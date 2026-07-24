"""Frozen minimization trajectory and checkpoint/restart comparison evidence.

The helpers in this module compare the already-retained operational and
independent coordinate traces without executing either minimizer.  They bind
exact step alignment, predefined coordinate/energy tolerances, aggregate
errors, and the three frozen checkpoint/restart cases.  A comparison document
is evidence about one synthetic S0 case only; it is not a production receipt
or a scientific/product promotion token.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_protocol_document,
)


REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trajectory_comparison_contract/1.2.0"
)
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trajectory_comparison/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_STEP_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_trajectory_step_comparison/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_RESTART_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_checkpoint_restart_evidence/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_ID = (
    "cpu_reference_minimization_validation_trajectory_comparison/1.2.0"
)
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_VERSION = "1.2.0"
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_FROZEN_AT_UTC = "2026-07-24T00:00:00Z"
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM = 1.0e-8
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL = 1.0e-10
REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES = (
    ("v1_checkpoint_restart_exact", 3),
    ("v2_constrained_checkpoint_restart_exact", 3),
    ("v2_fixed_born_checkpoint_restart_exact", 3),
)

FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256_V1_1 = (
    "5632e3bc397222757355b46b041bedb84952ff803735056b2b03597612dbead8"
)
FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256_V1_0 = (
    "588f07cfe239ffd418a4743522fb9a71910da62d9ac5452109234349f29e8a6f"
)
SUPERSEDED_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256 = (
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256_V1_1
)
REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_REFREEZE_REASON = (
    "binds_refrozen_compact_default_capacity_minimization_protocol"
)
FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256 = (
    "209223f4cc1afbe8e6b364a612335404afc8e4e002525eae68998e78e9b4fe8b"
)

TRAJECTORY_COMPARISON_ACCEPTED = "aligned_within_predefined_bounds"
TRAJECTORY_COMPARISON_REJECTED_ALIGNMENT = "rejected_alignment_mismatch"
TRAJECTORY_COMPARISON_REJECTED_THRESHOLD = "rejected_predefined_threshold"
TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED = "not_comparable_expected_fail_closed"
TRAJECTORY_COMPARISON_UNEXPECTED_FAILURE = "not_comparable_unexpected_failure"

CHECKPOINT_RESTART_VERIFIED = "checkpoint_restart_exactly_verified"
CHECKPOINT_RESTART_REJECTED = "checkpoint_restart_equality_rejected"
CHECKPOINT_RESTART_NOT_APPLICABLE = "not_applicable_no_checkpoint_case"
CHECKPOINT_RESTART_EXPECTED_FAIL_CLOSED = "not_comparable_expected_fail_closed"
CHECKPOINT_RESTART_UNEXPECTED_FAILURE = "not_evaluated_unexpected_failure"


class ReferenceMinimizationValidationTrajectoryComparisonError(ValueError):
    """Trajectory comparison evidence is incomplete or non-canonical."""


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
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "trajectory comparison evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} must be a lowercase SHA-256")
    return value


def _exact_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} must be a nonnegative integer")
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} must be a finite number")
    return result


def _finite_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} must be canonical binary64 hex")
    try:
        result = float.fromhex(value)
    except ValueError as exc:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            f"{name} must be canonical binary64 hex"
        ) from exc
    if not math.isfinite(result) or result.hex() != value:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} must be canonical finite binary64 hex")
    return result


def _comparison_case_rows() -> list[dict[str, Any]]:
    pause_by_case = dict(REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES)
    rows = []
    for ordinal, row in enumerate(
        cpu_minimization_validation_protocol_document()["case_manifest"]["cases"],
        start=1,
    ):
        rows.append(
            {
                "ordinal": ordinal,
                "case_id": row["case_id"],
                "expected_outcome": row["expected_outcome"],
                "checkpoint_pause_after_accepted_iterations": pause_by_case.get(row["case_id"]),
            }
        )
    return rows


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SCHEMA_ID),
        "contract_id": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_ID),
        "contract_version": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_VERSION),
        "frozen_at_utc": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_FROZEN_AT_UTC),
        "superseded_contract_sha256": (
            SUPERSEDED_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
        ),
        "refreeze_reason": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_REFREEZE_REASON),
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "purpose": {
            "lane": "synthetic_implementation_mathematics_only",
            "comparison_before_production_observation": True,
            "production_result_bundled": False,
            "scientific_promotion_authorized": False,
        },
        "case_contract": {
            "ordered_cases": _comparison_case_rows(),
            "operational_trace_source": "operational",
            "independent_trace_source": "independent_oracle",
            "expected_fail_closed_is_explicitly_non_comparable": True,
            "unexpected_missing_evaluation_is_rejected": True,
        },
        "alignment_contract": {
            "trace_length_equality_required": True,
            "evaluation_index_iteration_trial_outcome_equality_required": True,
            "branch_sequence_equality_required": True,
            "rejection_sequence_equality_required": True,
            "accepted_iteration_count_equality_required": True,
            "rejected_step_count_equality_required": True,
            "energy_force_evaluation_count_equality_required": True,
            "ordinal_pairing_without_exact_identity_allowed": False,
        },
        "numerical_contract": {
            "coordinate_unit": "angstrom",
            "energy_unit": "kcal/mol",
            "raw_coordinate_max_and_rms_required": True,
            "evaluated_coordinate_max_and_rms_required": True,
            "energy_max_and_rms_required": True,
            "coordinate_max_and_rms_threshold": (
                REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM
            ),
            "energy_max_and_rms_threshold": (
                REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL
            ),
            "thresholds_predefined_before_production_results": True,
            "nonfinite_values_rejected": True,
            "all_aligned_steps_including_rejections_in_aggregate": True,
        },
        "checkpoint_restart_contract": {
            "checkpoint_case_count": len(REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES),
            "checkpoint_cases": [
                {
                    "case_id": case_id,
                    "pause_after_accepted_iterations": pause,
                }
                for case_id, pause in (REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES)
            ],
            "uninterrupted_paused_and_resumed_state_digests_required": True,
            "uninterrupted_and_resumed_result_digest_equality_required": True,
            "uninterrupted_and_resumed_checkpoint_digest_equality_required": True,
            "uninterrupted_and_resumed_trajectory_digest_equality_required": True,
            "uninterrupted_and_resumed_counts_equality_required": True,
            "paused_accepted_iteration_count_must_equal_frozen_pause": True,
        },
        "schema_contract": {
            "comparison_schema_id": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_SCHEMA_ID),
            "step_comparison_schema_id": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_STEP_COMPARISON_SCHEMA_ID),
            "checkpoint_restart_schema_id": (REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_RESTART_EVIDENCE_SCHEMA_ID),
            "canonical_sha256_required_at_step_checkpoint_and_case_levels": True,
            "missing_reordered_crosswired_or_digest_tampered_rows_rejected": True,
        },
        "current_state": {
            "contract_frozen": True,
            "production_comparison_receipt_present": False,
            "two_cpu_host_reproduction_complete": False,
            "external_implementation_comparison_complete": False,
            "s0_accepted": False,
            "s1_admission": False,
        },
    }


def reference_minimization_validation_trajectory_comparison_contract_document() -> dict[str, Any]:
    """Return the frozen, pre-observation comparison contract."""

    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
        and document["contract_sha256"]
        != FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256
    ):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "frozen trajectory comparison contract SHA-256 drifted"
        )
    return document


def require_reference_minimization_validation_trajectory_comparison_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "trajectory comparison contract must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected = reference_minimization_validation_trajectory_comparison_contract_document()
    if observed != expected:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "trajectory comparison contract does not match the frozen record"
        )
    return observed


def _checkpoint_state_row(value: Mapping[str, Any], *, name: str) -> dict[str, Any]:
    required = {
        "status",
        "failure_code",
        "result_sha256",
        "checkpoint_sha256",
        "trajectory_sha256",
        "accepted_iteration_count",
        "rejected_step_count",
        "energy_force_evaluation_count",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} state fields are invalid")
    status = value["status"]
    failure_code = value["failure_code"]
    if not isinstance(status, str) or not status:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} status is invalid")
    if failure_code is not None and (not isinstance(failure_code, str) or not failure_code):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} failure code is invalid")
    return {
        "status": status,
        "failure_code": failure_code,
        "result_sha256": _require_sha256(value["result_sha256"], name=f"{name} result"),
        "checkpoint_sha256": _require_sha256(value["checkpoint_sha256"], name=f"{name} checkpoint"),
        "trajectory_sha256": _require_sha256(value["trajectory_sha256"], name=f"{name} trajectory"),
        "accepted_iteration_count": _exact_nonnegative_int(
            value["accepted_iteration_count"],
            name=f"{name} accepted iteration count",
        ),
        "rejected_step_count": _exact_nonnegative_int(value["rejected_step_count"], name=f"{name} rejected step count"),
        "energy_force_evaluation_count": _exact_nonnegative_int(
            value["energy_force_evaluation_count"],
            name=f"{name} energy-force evaluation count",
        ),
    }


def _checkpoint_payload(
    *,
    case_id: str,
    expected_outcome: str,
    uninterrupted: Mapping[str, Any] | None,
    paused: Mapping[str, Any] | None,
    resumed: Mapping[str, Any] | None,
) -> dict[str, Any]:
    pause_by_case = dict(REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES)
    pause = pause_by_case.get(case_id)
    supplied = (uninterrupted, paused, resumed)
    if expected_outcome == "fail_closed":
        if any(row is not None for row in supplied):
            raise ReferenceMinimizationValidationTrajectoryComparisonError(
                "expected fail-closed case cannot carry checkpoint execution states"
            )
        disposition = CHECKPOINT_RESTART_EXPECTED_FAIL_CLOSED
        passed = True
        rows: tuple[dict[str, Any] | None, ...] = (None, None, None)
    elif pause is None:
        if any(row is not None for row in supplied):
            raise ReferenceMinimizationValidationTrajectoryComparisonError(
                "non-checkpoint case cannot carry checkpoint execution states"
            )
        disposition = CHECKPOINT_RESTART_NOT_APPLICABLE
        passed = True
        rows = (None, None, None)
    elif all(row is None for row in supplied):
        disposition = CHECKPOINT_RESTART_UNEXPECTED_FAILURE
        passed = False
        rows = (None, None, None)
    elif any(row is None for row in supplied):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("checkpoint execution states must be complete")
    else:
        normalized = tuple(
            _checkpoint_state_row(row, name=name)
            for row, name in zip(
                supplied,
                ("uninterrupted", "paused", "resumed"),
                strict=True,
            )
            if row is not None
        )
        uninterrupted_row, paused_row, resumed_row = normalized
        result_equal = uninterrupted_row["result_sha256"] == resumed_row["result_sha256"]
        checkpoint_equal = uninterrupted_row["checkpoint_sha256"] == resumed_row["checkpoint_sha256"]
        trajectory_equal = uninterrupted_row["trajectory_sha256"] == resumed_row["trajectory_sha256"]
        counts_equal = all(
            uninterrupted_row[key] == resumed_row[key]
            for key in (
                "accepted_iteration_count",
                "rejected_step_count",
                "energy_force_evaluation_count",
            )
        )
        paused_at_frozen_iteration = (
            paused_row["accepted_iteration_count"] == pause
            and paused_row["status"] == "checkpointed"
            and paused_row["failure_code"] is None
        )
        passed = result_equal and checkpoint_equal and trajectory_equal and counts_equal and paused_at_frozen_iteration
        disposition = CHECKPOINT_RESTART_VERIFIED if passed else CHECKPOINT_RESTART_REJECTED
        rows = normalized
    payload = {
        "schema_id": (REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_RESTART_EVIDENCE_SCHEMA_ID),
        "comparison_contract_sha256": (FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256),
        "case_id": case_id,
        "expected_outcome": expected_outcome,
        "pause_after_accepted_iterations": pause,
        "uninterrupted": rows[0],
        "paused": rows[1],
        "resumed": rows[2],
        "result_digest_equality": (None if rows[0] is None else rows[0]["result_sha256"] == rows[2]["result_sha256"]),
        "checkpoint_digest_equality": (
            None if rows[0] is None else rows[0]["checkpoint_sha256"] == rows[2]["checkpoint_sha256"]
        ),
        "trajectory_digest_equality": (
            None if rows[0] is None else rows[0]["trajectory_sha256"] == rows[2]["trajectory_sha256"]
        ),
        "uninterrupted_resumed_count_equality": (
            None
            if rows[0] is None
            else all(
                rows[0][key] == rows[2][key]
                for key in (
                    "accepted_iteration_count",
                    "rejected_step_count",
                    "energy_force_evaluation_count",
                )
            )
        ),
        "checkpoint_restart_disposition": disposition,
        "checkpoint_restart_passed": passed,
    }
    return payload


def build_reference_minimization_validation_checkpoint_restart_evidence(
    *,
    case_id: str,
    expected_outcome: str,
    uninterrupted: Mapping[str, Any] | None = None,
    paused: Mapping[str, Any] | None = None,
    resumed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _checkpoint_payload(
        case_id=case_id,
        expected_outcome=expected_outcome,
        uninterrupted=uninterrupted,
        paused=paused,
        resumed=resumed,
    )
    payload["checkpoint_restart_evidence_sha256"] = _sha256(payload)
    return payload


def require_reference_minimization_validation_checkpoint_restart_evidence(
    value: Mapping[str, Any],
    *,
    expected_case_id: str,
    expected_outcome: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("checkpoint/restart evidence must be a mapping")
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    required = {
        "schema_id",
        "comparison_contract_sha256",
        "case_id",
        "expected_outcome",
        "pause_after_accepted_iterations",
        "uninterrupted",
        "paused",
        "resumed",
        "result_digest_equality",
        "checkpoint_digest_equality",
        "trajectory_digest_equality",
        "uninterrupted_resumed_count_equality",
        "checkpoint_restart_disposition",
        "checkpoint_restart_passed",
        "checkpoint_restart_evidence_sha256",
    }
    if set(observed) != required:
        raise ReferenceMinimizationValidationTrajectoryComparisonError("checkpoint/restart evidence fields are invalid")
    if observed["case_id"] != expected_case_id or observed["expected_outcome"] != expected_outcome:
        raise ReferenceMinimizationValidationTrajectoryComparisonError("checkpoint/restart evidence is cross-wired")
    expected = build_reference_minimization_validation_checkpoint_restart_evidence(
        case_id=expected_case_id,
        expected_outcome=expected_outcome,
        uninterrupted=observed["uninterrupted"],
        paused=observed["paused"],
        resumed=observed["resumed"],
    )
    if observed != expected:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "checkpoint/restart evidence is non-canonical or tampered"
        )
    return observed


def _trace(value: Mapping[str, Any], *, source: str, case_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("coordinate trace must be a mapping")
    row = dict(value)
    if row.get("case_id") != case_id or row.get("trace_source") != source:
        raise ReferenceMinimizationValidationTrajectoryComparisonError("coordinate trace is cross-wired")
    _require_sha256(row.get("trace_sha256"), name=f"{source} trace")
    steps = row.get("steps")
    if not isinstance(steps, list):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("coordinate trace steps must be a list")
    if row.get("trace_length") != len(steps):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("coordinate trace length is invalid")
    for name in (
        "accepted_iteration_count",
        "rejected_step_count",
        "energy_force_evaluation_count",
    ):
        _exact_nonnegative_int(row.get(name), name=f"{source} {name}")
    return row


def _step_identity(step: Mapping[str, Any]) -> tuple[int, int, int, str]:
    if not isinstance(step, Mapping):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("coordinate trace step must be a mapping")
    evaluation_index = _exact_nonnegative_int(step.get("evaluation_index"), name="step evaluation index")
    iteration = _exact_nonnegative_int(step.get("iteration"), name="step iteration")
    trial = _exact_nonnegative_int(step.get("trial"), name="step trial")
    outcome = step.get("outcome")
    if not isinstance(outcome, str) or not outcome:
        raise ReferenceMinimizationValidationTrajectoryComparisonError("step outcome is invalid")
    _require_sha256(step.get("step_identity_sha256"), name="trace step identity")
    return evaluation_index, iteration, trial, outcome


def _coordinate_differences(
    first: object,
    second: object,
    *,
    name: str,
) -> list[float]:
    if not isinstance(first, list) or not isinstance(second, list) or len(first) != len(second):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} coordinate shapes disagree")
    differences: list[float] = []
    for first_row, second_row in zip(first, second, strict=True):
        if (
            not isinstance(first_row, list)
            or not isinstance(second_row, list)
            or len(first_row) != 3
            or len(second_row) != 3
        ):
            raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} coordinate rows are invalid")
        differences.extend(
            _finite_hex(left, name=f"{name} coordinate") - _finite_hex(right, name=f"{name} coordinate")
            for left, right in zip(first_row, second_row, strict=True)
        )
    if not differences:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(f"{name} coordinates cannot be empty")
    return differences


def _max_rms(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ReferenceMinimizationValidationTrajectoryComparisonError("comparison values cannot be empty")
    maximum = max(abs(value) for value in values)
    rms = math.sqrt(math.fsum(value * value for value in values) / len(values))
    if not math.isfinite(maximum) or not math.isfinite(rms):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("comparison produced a non-finite error")
    return maximum, rms


def _step_comparison(
    *,
    case_id: str,
    ordinal: int,
    operational: Mapping[str, Any],
    independent: Mapping[str, Any],
) -> tuple[dict[str, Any], list[float], list[float], float]:
    operational_identity = _step_identity(operational)
    independent_identity = _step_identity(independent)
    if operational_identity != independent_identity:
        raise ReferenceMinimizationValidationTrajectoryComparisonError("unaligned steps cannot be numerically compared")
    raw = _coordinate_differences(
        operational.get("raw_coordinates_angstrom_hex"),
        independent.get("raw_coordinates_angstrom_hex"),
        name="raw",
    )
    evaluated = _coordinate_differences(
        operational.get("evaluated_coordinates_angstrom_hex"),
        independent.get("evaluated_coordinates_angstrom_hex"),
        name="evaluated",
    )
    operational_energy = _finite(operational.get("energy_kcal_per_mol"), name="operational step energy")
    independent_energy = _finite(independent.get("energy_kcal_per_mol"), name="independent step energy")
    raw_maximum, raw_rms = _max_rms(raw)
    evaluated_maximum, evaluated_rms = _max_rms(evaluated)
    energy_error = abs(operational_energy - independent_energy)
    coordinate_threshold = REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM
    energy_threshold = REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL
    passed = (
        raw_maximum <= coordinate_threshold
        and raw_rms <= coordinate_threshold
        and evaluated_maximum <= coordinate_threshold
        and evaluated_rms <= coordinate_threshold
        and energy_error <= energy_threshold
    )
    payload = {
        "schema_id": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_STEP_COMPARISON_SCHEMA_ID),
        "case_id": case_id,
        "comparison_ordinal": ordinal,
        "evaluation_index": operational_identity[0],
        "iteration": operational_identity[1],
        "trial": operational_identity[2],
        "outcome": operational_identity[3],
        "operational_step_identity_sha256": _require_sha256(
            operational.get("step_identity_sha256"),
            name="operational step identity",
        ),
        "independent_step_identity_sha256": _require_sha256(
            independent.get("step_identity_sha256"),
            name="independent step identity",
        ),
        "raw_coordinate_scalar_count": len(raw),
        "raw_coordinate_max_abs_error_angstrom": raw_maximum,
        "raw_coordinate_rms_error_angstrom": raw_rms,
        "evaluated_coordinate_scalar_count": len(evaluated),
        "evaluated_coordinate_max_abs_error_angstrom": evaluated_maximum,
        "evaluated_coordinate_rms_error_angstrom": evaluated_rms,
        "energy_abs_error_kcal_per_mol": energy_error,
        "coordinate_threshold_angstrom": coordinate_threshold,
        "energy_threshold_kcal_per_mol": energy_threshold,
        "step_comparison_disposition": (
            TRAJECTORY_COMPARISON_ACCEPTED if passed else TRAJECTORY_COMPARISON_REJECTED_THRESHOLD
        ),
        "step_comparison_passed": passed,
    }
    payload["step_comparison_sha256"] = _sha256(payload)
    return payload, raw, evaluated, operational_energy - independent_energy


def _same_count(first: Mapping[str, Any], second: Mapping[str, Any], key: str) -> bool:
    return _exact_nonnegative_int(first.get(key), name=f"operational {key}") == (
        _exact_nonnegative_int(second.get(key), name=f"independent {key}")
    )


def _trajectory_payload(
    *,
    case_id: str,
    expected_outcome: str,
    operational_trace: Mapping[str, Any],
    independent_trace: Mapping[str, Any],
) -> dict[str, Any]:
    operational = _trace(operational_trace, source="operational", case_id=case_id)
    independent = _trace(independent_trace, source="independent_oracle", case_id=case_id)
    operational_steps = operational["steps"]
    independent_steps = independent["steps"]
    not_comparable: str | None = None
    if expected_outcome == "fail_closed":
        not_comparable = TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED
    elif operational.get("trace_state") != "evaluated" or independent.get("trace_state") != "evaluated":
        not_comparable = TRAJECTORY_COMPARISON_UNEXPECTED_FAILURE

    if not_comparable is not None:
        expected_noncomparable_state = (
            expected_outcome == "fail_closed"
            and operational.get("trace_state") == "not_evaluated_expected_fail_closed"
            and not operational_steps
        )
        passed = expected_noncomparable_state
        return {
            "operational_trace_sha256": operational["trace_sha256"],
            "independent_trace_sha256": independent["trace_sha256"],
            "operational_trace_length": len(operational_steps),
            "independent_trace_length": len(independent_steps),
            "aligned_step_count": 0,
            "trace_length_disposition": not_comparable,
            "step_identity_alignment_disposition": not_comparable,
            "branch_sequence_disposition": not_comparable,
            "rejection_sequence_disposition": not_comparable,
            "accepted_iteration_count_disposition": not_comparable,
            "rejected_step_count_disposition": not_comparable,
            "energy_force_evaluation_count_disposition": not_comparable,
            "raw_coordinate_scalar_count": 0,
            "raw_coordinate_max_abs_error_angstrom": None,
            "raw_coordinate_rms_error_angstrom": None,
            "evaluated_coordinate_scalar_count": 0,
            "evaluated_coordinate_max_abs_error_angstrom": None,
            "evaluated_coordinate_rms_error_angstrom": None,
            "energy_value_count": 0,
            "energy_max_abs_error_kcal_per_mol": None,
            "energy_rms_error_kcal_per_mol": None,
            "coordinate_threshold_angstrom": (
                REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM
            ),
            "energy_threshold_kcal_per_mol": (
                REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL
            ),
            "step_comparisons": [],
            "trajectory_comparison_disposition": not_comparable,
            "trajectory_comparison_passed": passed,
        }

    length_equal = len(operational_steps) == len(independent_steps)
    identities_equal = length_equal and all(
        _step_identity(left) == _step_identity(right)
        for left, right in zip(operational_steps, independent_steps, strict=True)
    )
    branch_equal = identities_equal
    operational_rejections = [
        _step_identity(row) for row in operational_steps if str(row.get("outcome", "")).startswith("rejected_")
    ]
    independent_rejections = [
        _step_identity(row) for row in independent_steps if str(row.get("outcome", "")).startswith("rejected_")
    ]
    rejection_equal = operational_rejections == independent_rejections
    accepted_count_equal = _same_count(operational, independent, "accepted_iteration_count")
    rejected_count_equal = _same_count(operational, independent, "rejected_step_count")
    evaluation_count_equal = _same_count(operational, independent, "energy_force_evaluation_count")
    aligned = (
        length_equal
        and identities_equal
        and branch_equal
        and rejection_equal
        and accepted_count_equal
        and rejected_count_equal
        and evaluation_count_equal
    )
    step_rows: list[dict[str, Any]] = []
    raw_values: list[float] = []
    evaluated_values: list[float] = []
    energy_values: list[float] = []
    if aligned:
        for ordinal, (left, right) in enumerate(zip(operational_steps, independent_steps, strict=True), start=1):
            row, raw, evaluated, energy = _step_comparison(
                case_id=case_id,
                ordinal=ordinal,
                operational=left,
                independent=right,
            )
            step_rows.append(row)
            raw_values.extend(raw)
            evaluated_values.extend(evaluated)
            energy_values.append(energy)

    if aligned and step_rows:
        raw_maximum, raw_rms = _max_rms(raw_values)
        evaluated_maximum, evaluated_rms = _max_rms(evaluated_values)
        energy_maximum, energy_rms = _max_rms(energy_values)
        numerical_passed = all(row["step_comparison_passed"] for row in step_rows)
        disposition = TRAJECTORY_COMPARISON_ACCEPTED if numerical_passed else TRAJECTORY_COMPARISON_REJECTED_THRESHOLD
    else:
        raw_maximum = raw_rms = None
        evaluated_maximum = evaluated_rms = None
        energy_maximum = energy_rms = None
        numerical_passed = False
        disposition = TRAJECTORY_COMPARISON_REJECTED_ALIGNMENT
    return {
        "operational_trace_sha256": operational["trace_sha256"],
        "independent_trace_sha256": independent["trace_sha256"],
        "operational_trace_length": len(operational_steps),
        "independent_trace_length": len(independent_steps),
        "aligned_step_count": len(step_rows),
        "trace_length_disposition": "equal" if length_equal else "mismatch",
        "step_identity_alignment_disposition": ("equal" if identities_equal else "mismatch"),
        "branch_sequence_disposition": "equal" if branch_equal else "mismatch",
        "rejection_sequence_disposition": ("equal" if rejection_equal else "mismatch"),
        "accepted_iteration_count_disposition": ("equal" if accepted_count_equal else "mismatch"),
        "rejected_step_count_disposition": ("equal" if rejected_count_equal else "mismatch"),
        "energy_force_evaluation_count_disposition": ("equal" if evaluation_count_equal else "mismatch"),
        "raw_coordinate_scalar_count": len(raw_values),
        "raw_coordinate_max_abs_error_angstrom": raw_maximum,
        "raw_coordinate_rms_error_angstrom": raw_rms,
        "evaluated_coordinate_scalar_count": len(evaluated_values),
        "evaluated_coordinate_max_abs_error_angstrom": evaluated_maximum,
        "evaluated_coordinate_rms_error_angstrom": evaluated_rms,
        "energy_value_count": len(energy_values),
        "energy_max_abs_error_kcal_per_mol": energy_maximum,
        "energy_rms_error_kcal_per_mol": energy_rms,
        "coordinate_threshold_angstrom": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM),
        "energy_threshold_kcal_per_mol": (REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL),
        "step_comparisons": step_rows,
        "trajectory_comparison_disposition": disposition,
        "trajectory_comparison_passed": numerical_passed,
    }


def build_reference_minimization_validation_trajectory_comparison(
    *,
    case_id: str,
    expected_outcome: str,
    operational_trace: Mapping[str, Any],
    independent_trace: Mapping[str, Any],
    checkpoint_restart_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    checkpoint = require_reference_minimization_validation_checkpoint_restart_evidence(
        checkpoint_restart_evidence,
        expected_case_id=case_id,
        expected_outcome=expected_outcome,
    )
    trajectory = _trajectory_payload(
        case_id=case_id,
        expected_outcome=expected_outcome,
        operational_trace=operational_trace,
        independent_trace=independent_trace,
    )
    payload = {
        "schema_id": REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_SCHEMA_ID,
        "comparison_contract_sha256": (FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256),
        "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
        "case_id": case_id,
        "expected_outcome": expected_outcome,
        **trajectory,
        "checkpoint_restart_evidence": checkpoint,
        "comparison_passed": (trajectory["trajectory_comparison_passed"] and checkpoint["checkpoint_restart_passed"]),
        "production_comparison_receipt": False,
        "scientifically_validated": False,
        "s1_admission": False,
    }
    payload["comparison_sha256"] = _sha256(payload)
    return payload


def require_reference_minimization_validation_trajectory_comparison(
    value: Mapping[str, Any],
    *,
    expected_case_id: str,
    expected_outcome: str,
    operational_trace: Mapping[str, Any],
    independent_trace: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceMinimizationValidationTrajectoryComparisonError("trajectory comparison must be a mapping")
    observed = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    checkpoint = observed.get("checkpoint_restart_evidence")
    if not isinstance(checkpoint, Mapping):
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "trajectory comparison omitted checkpoint/restart evidence"
        )
    expected = build_reference_minimization_validation_trajectory_comparison(
        case_id=expected_case_id,
        expected_outcome=expected_outcome,
        operational_trace=operational_trace,
        independent_trace=independent_trace,
        checkpoint_restart_evidence=checkpoint,
    )
    if observed != expected:
        raise ReferenceMinimizationValidationTrajectoryComparisonError(
            "trajectory comparison is missing, reordered, cross-wired, or tampered"
        )
    return observed


def reference_minimization_validation_trajectory_comparison_contract_decision() -> dict[str, Any]:
    contract = reference_minimization_validation_trajectory_comparison_contract_document()
    return {
        "comparison_contract_sha256": contract["contract_sha256"],
        "trajectory_comparison_contract_frozen": True,
        "production_comparison_receipt_present": False,
        "two_cpu_host_reproduction_complete": False,
        "external_implementation_comparison_complete": False,
        "s0_accepted": False,
        "s1_admission": False,
    }


__all__ = [
    "CHECKPOINT_RESTART_EXPECTED_FAIL_CLOSED",
    "CHECKPOINT_RESTART_NOT_APPLICABLE",
    "CHECKPOINT_RESTART_REJECTED",
    "CHECKPOINT_RESTART_UNEXPECTED_FAILURE",
    "CHECKPOINT_RESTART_VERIFIED",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256_V1_0",
    "FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256_V1_1",
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_CASE_PAUSES",
    "REFERENCE_MINIMIZATION_VALIDATION_CHECKPOINT_RESTART_EVIDENCE_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_CONTRACT_VERSION",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COMPARISON_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_COORDINATE_THRESHOLD_ANGSTROM",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_ENERGY_THRESHOLD_KCAL_PER_MOL",
    "REFERENCE_MINIMIZATION_VALIDATION_TRAJECTORY_STEP_COMPARISON_SCHEMA_ID",
    "ReferenceMinimizationValidationTrajectoryComparisonError",
    "TRAJECTORY_COMPARISON_ACCEPTED",
    "TRAJECTORY_COMPARISON_EXPECTED_FAIL_CLOSED",
    "TRAJECTORY_COMPARISON_REJECTED_ALIGNMENT",
    "TRAJECTORY_COMPARISON_REJECTED_THRESHOLD",
    "TRAJECTORY_COMPARISON_UNEXPECTED_FAILURE",
    "build_reference_minimization_validation_checkpoint_restart_evidence",
    "build_reference_minimization_validation_trajectory_comparison",
    "reference_minimization_validation_trajectory_comparison_contract_decision",
    "reference_minimization_validation_trajectory_comparison_contract_document",
    "require_reference_minimization_validation_checkpoint_restart_evidence",
    "require_reference_minimization_validation_trajectory_comparison",
    "require_reference_minimization_validation_trajectory_comparison_contract_document",
]
