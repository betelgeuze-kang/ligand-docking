"""Independent post-result review for the frozen energy/force validation lane.

The pre-execution scientific-review and execution-authorization artifacts in
this lane are legacy symmetric-HMAC records.  This leaf review uses Ed25519 so
that a verifier needs only a result-reviewer public key, but it deliberately
does not describe the upstream HMAC chain as asymmetric or as external
custody.  A verified review remains synthetic implementation evidence only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping, Sequence

from .reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    sign_ed25519,
    verify_ed25519,
)
from .reference_parameter_applicability import (
    FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256,
)
from .reference_validation_artifact_binding import (
    FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from .reference_validation_authorization import (
    FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    AuthorizationOperatorTrustAnchor,
    ReferenceValidationAuthorizationError,
    verify_signed_reference_validation_authorization_receipt,
)
from .reference_validation_bootstrap import (
    REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
)
from .reference_validation_materializer import (
    reference_validation_materialization_manifest_document,
)
from .reference_validation_protocol import (
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
    cpu_reference_validation_protocol_document,
)
from .reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
    REFERENCE_VALIDATION_RESULT_RECEIPT_SCHEMA_ID,
)
from .reference_validation_result_writer import (
    FROZEN_REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
    ReferenceValidationResultReceipt,
    ReferenceValidationResultWriterError,
)
from .reference_validation_review import (
    FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
    ScientificReviewerTrustAnchor,
)
from .reference_validation_runner import (
    FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
    REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID,
    REFERENCE_VALIDATION_WORKER_FRAME_SCHEMA_ID,
)


REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_result_review_contract/1.0.0"
)
REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_result_review_attestation/1.0.0"
)
REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_ID = (
    "cpu_reference_energy_force_independent_result_review_contract/1.0.0"
)
REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_VERSION = "1.0.0"
REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_FROZEN_AT_UTC = "2026-07-19T01:00:00Z"
REFERENCE_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM = "ed25519"
REFERENCE_VALIDATION_RESULT_REVIEW_MAX_VALIDITY = timedelta(days=30)

RESULT_REVIEW_OUTCOME_ACCEPTED = "accepted"
RESULT_REVIEW_OUTCOME_REJECTED = "rejected"
CASE_DISPOSITION_ACCEPTED = "case_result_accepted"
CASE_DISPOSITION_REJECTED = "case_result_rejected"
VARIANT_DISPOSITION_ACCEPTED = "variant_result_accepted"
VARIANT_DISPOSITION_REJECTED = "variant_result_rejected"
METRIC_DISPOSITION_ACCEPTED = "metric_value_accepted"
METRIC_DISPOSITION_REJECTED = "metric_value_rejected"
FAILURE_DISPOSITION_ACCEPTED = "expected_failure_accepted"
FAILURE_DISPOSITION_REJECTED = "failure_result_rejected"
WORKER_EXECUTION_DISPOSITION_ACCEPTED = "worker_execution_evidence_accepted"
WORKER_EXECUTION_DISPOSITION_REJECTED = "worker_execution_evidence_rejected"

_COMPONENT_ENERGY_NAMES_SORTED = (
    "harmonic_angle",
    "harmonic_bond",
    "lennard_jones",
    "periodic_torsion",
    "screened_coulomb",
)
_COMPONENT_TOTAL_SUM_ORDER = (
    "harmonic_bond",
    "harmonic_angle",
    "periodic_torsion",
    "lennard_jones",
    "screened_coulomb",
)
_CENTRAL_DIFFERENCE_STEP_ANGSTROM = 1.0e-5
_RELATIVE_ERROR_DENOMINATOR_FLOOR = 1.0e-12
_ROTATION_MATRIX = (
    (0.0, -1.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
)
_PERMUTATION_NEW_TO_OLD = (3, 1, 0, 2)
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

# Filled after the frozen projection is finalized.  Contract access fails
# closed if source or any bound dependency drifts.
FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256 = (
    "6c8cfb583f6d52ca17338fa0e84d5c5740da0820750dd9d99df1f309b888140a"
)

_REQUIRED_RESULT_REVIEW_CHECK_IDS = (
    "exact_receipt_self_hash_schema_and_out_of_band_identity_reviewed",
    "protocol_artifact_writer_runner_and_environment_chain_reviewed",
    "ordered_twenty_seven_cases_and_fifty_nine_variants_reviewed",
    "all_nineteen_metric_contracts_and_fifty_six_occurrences_reviewed",
    "metric_values_units_operators_and_thresholds_independently_recomputed",
    "successful_variant_input_component_total_and_force_evidence_reviewed",
    "all_case_variant_metric_and_failure_dispositions_derived",
    "manifest_and_case_worker_requests_transcripts_frames_and_pids_reviewed",
    "raw_upstream_hmac_review_authorization_and_four_role_chain_reviewed",
    "freshness_revocation_and_supersession_state_reviewed",
    "nonpromotion_and_synthetic_parameter_limitations_acknowledged",
)
_REQUIRED_LIMITATION_IDS = (
    "energy_force_upstream_review_and_authorization_use_symmetric_hmac",
    "ed25519_leaf_review_does_not_make_the_upstream_chain_asymmetric",
    "synthetic_fixture_values_are_not_reviewed_runtime_parameter_values",
    "contract_result_review_is_not_scientific_force_field_validation",
    "result_review_does_not_establish_two_host_reproducibility",
    "result_review_does_not_establish_external_implementation_comparison",
    "result_review_does_not_establish_chemical_applicability",
    "result_review_does_not_authorize_parameter_fitting_or_product_promotion",
    "test_only_result_review_attestation_is_not_production_evidence",
)
_CLOSED_GATE_BLOCKERS = (
    "signed_independent_result_review_attestation_missing",
    "trusted_independent_result_reviewer_key_not_provided",
    "production_result_receipt_missing",
    "independent_human_production_result_approval_missing",
    "energy_force_upstream_symmetric_hmac_chain",
    "independent_result_review_dependency_manifest_reverification_missing",
    "result_receipt_external_authenticity_or_custody_missing",
    "worker_process_starttime_and_boot_id_binding_missing",
    "two_cpu_host_reproducibility_missing",
    "independent_external_implementation_comparison_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_POST_ATTESTATION_BLOCKERS = (
    "production_result_receipt_missing",
    "test_only_result_review_attestation_is_not_production_evidence",
    "independent_human_production_result_approval_missing",
    "energy_force_upstream_symmetric_hmac_chain",
    "independent_result_review_dependency_manifest_reverification_missing",
    "result_receipt_external_authenticity_or_custody_missing",
    "worker_process_starttime_and_boot_id_binding_missing",
    "two_cpu_host_reproducibility_missing",
    "independent_external_implementation_comparison_missing",
    "scientific_parameter_applicability_not_established",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_REJECTED_RESULT_BLOCKERS = (
    "energy_force_result_receipt_review_rejected",
    *_POST_ATTESTATION_BLOCKERS,
)


class ReferenceValidationResultReviewError(ValueError):
    """The energy/force result-review artifact or trust input is invalid."""


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
        raise ReferenceValidationResultReviewError(
            "result review artifact is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationResultReviewError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_commit_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationResultReviewError(
            f"{name} must be a lowercase Git commit SHA"
        )
    return value


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReferenceValidationResultReviewError(
            f"{name} must be second-resolution UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceValidationResultReviewError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationResultReviewError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationResultReviewError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_key(value: bytes | str, *, name: str) -> bytes:
    key = value.encode("utf-8") if isinstance(value, str) else value
    if not isinstance(key, bytes) or len(key) != 32:
        raise ReferenceValidationResultReviewError(
            f"{name} must contain exactly 32 bytes"
        )
    return key


def _require_key_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReferenceValidationResultReviewError(
            "result reviewer key id must contain 1 to 128 characters"
        )
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if any(character not in allowed for character in value):
        raise ReferenceValidationResultReviewError(
            "result reviewer key id contains unsupported characters"
        )
    return value


def _external_sha256_set(values: Sequence[str], *, name: str) -> set[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ReferenceValidationResultReviewError(
            f"{name} must be an explicit sequence of SHA-256 values"
        )
    return {_require_sha256(value, name=name) for value in values}


def _is_finite_number(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _validated_result_receipt_document(
    result_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(result_receipt, Mapping):
        raise ReferenceValidationResultReviewError("result receipt must be a mapping")
    document = json.loads(_canonical_bytes(dict(result_receipt)).decode("ascii"))
    receipt_sha256 = _require_sha256(
        document.get("receipt_sha256"), name="result receipt"
    )
    try:
        validated = ReferenceValidationResultReceipt(
            receipt_sha256=receipt_sha256,
            canonical_document_bytes=_canonical_bytes(document),
        )
    except ReferenceValidationResultWriterError as exc:
        raise ReferenceValidationResultReviewError(
            "result receipt failed full result-writer contract validation"
        ) from exc
    return validated.to_dict()


def _protocol_and_materialization() -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = cpu_reference_validation_protocol_document()
    materialization = reference_validation_materialization_manifest_document()
    protocol_cases = protocol["fixture_manifest"]["cases"]
    materialized_cases = materialization["cases"]
    metrics = protocol["numerical_protocol"]["metrics"]
    if (
        len(protocol_cases) != 27
        or len(materialized_cases) != 27
        or len(metrics) != 19
        or sum(len(case["variants"]) for case in materialized_cases) != 59
        or sum(len(case["required_metric_ids"]) for case in protocol_cases) != 56
        or sum(case["expected_outcome"] == "pass" for case in protocol_cases) != 15
        or sum(case["expected_outcome"] == "fail_closed" for case in protocol_cases)
        != 12
    ):
        raise ReferenceValidationResultReviewError(
            "frozen energy/force protocol coverage drifted"
        )
    for protocol_case, materialized_case in zip(
        protocol_cases, materialized_cases, strict=True
    ):
        if protocol_case["case_id"] != materialized_case["case_id"]:
            raise ReferenceValidationResultReviewError(
                "protocol and materialization case order diverged"
            )
    return protocol, materialization


def _metric_contract_map() -> dict[str, dict[str, Any]]:
    protocol, _ = _protocol_and_materialization()
    rows = protocol["numerical_protocol"]["metrics"]
    result = {row["metric_id"]: dict(row) for row in rows}
    if len(result) != 19:
        raise ReferenceValidationResultReviewError(
            "metric contract identities are not unique"
        )
    return result


def _metric_passed(contract: Mapping[str, Any], value: object) -> bool:
    operator = contract["threshold_operator"]
    threshold = contract["threshold_value"]
    if operator == "equal":
        if type(value) is not bool or contract["unit"] != "boolean":
            return False
        return value == bool(threshold)
    if operator == "less_than_or_equal":
        return (
            _is_finite_number(value)
            and float(value) >= 0.0
            and float(value) <= float(threshold)
        )
    raise ReferenceValidationResultReviewError(
        "frozen metric threshold operator is unsupported"
    )


def _force_array_sha256(value: object) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    values_hex: list[list[str]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            return None
        hex_row: list[str] = []
        for item in row:
            if not _is_finite_number(item):
                return None
            hex_row.append(float(item).hex())
        values_hex.append(hex_row)
    return _sha256(
        {
            "shape": [len(value), 3],
            "dtype": "float64",
            "unit": "kcal/mol/angstrom",
            "values_hex": values_hex,
        }
    )


def _successful_variant_evidence_review(
    variant: Mapping[str, Any],
    *,
    expected_atom_count: int,
) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    component_rows = variant.get("component_energy_values_and_units")
    if not isinstance(component_rows, list) or not component_rows:
        component_rows = []
        reasons.append("component_energy_evidence_missing")
    component_names: list[str] = []
    for row in component_rows:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"name", "value", "unit"}
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or row.get("unit") != "kcal/mol"
            or not _is_finite_number(row.get("value"))
        ):
            reasons.append("component_energy_evidence_invalid")
            continue
        component_names.append(row["name"])
    if tuple(component_names) != _COMPONENT_ENERGY_NAMES_SORTED:
        reasons.append("component_energy_order_or_identity_invalid")

    total_energy = variant.get("total_energy_value")
    if variant.get("total_energy_unit") != "kcal/mol" or not _is_finite_number(
        total_energy
    ):
        reasons.append("total_energy_evidence_invalid")
    component_total: float | None = None
    if tuple(component_names) == _COMPONENT_ENERGY_NAMES_SORTED:
        component_map = {row["name"]: float(row["value"]) for row in component_rows}
        component_total = sum(
            (component_map[name] for name in _COMPONENT_TOTAL_SUM_ORDER),
            0.0,
        )
        if (
            not _is_finite_number(total_energy)
            or component_total.hex() != float(total_energy).hex()
        ):
            reasons.append("component_energy_sum_does_not_equal_total_energy")
    if variant.get("oracle_total_energy_unit") != "kcal/mol" or not _is_finite_number(
        variant.get("oracle_total_energy_value")
    ):
        reasons.append("oracle_total_energy_evidence_invalid")

    force_values = variant.get("force_array_values")
    oracle_force_values = variant.get("oracle_force_array_values")
    force_sha256 = _force_array_sha256(force_values)
    oracle_force_sha256 = _force_array_sha256(oracle_force_values)
    shape = variant.get("force_array_shape")
    if (
        force_sha256 is None
        or force_sha256 != variant.get("force_array_sha256")
        or not isinstance(force_values, list)
        or len(force_values) != expected_atom_count
        or shape != [len(force_values), 3]
        or variant.get("force_array_dtype") != "float64"
        or variant.get("force_array_unit") != "kcal/mol/angstrom"
    ):
        reasons.append("force_array_evidence_invalid")
    if (
        oracle_force_sha256 is None
        or oracle_force_sha256 != variant.get("oracle_force_array_sha256")
        or not isinstance(oracle_force_values, list)
        or not isinstance(force_values, list)
        or len(oracle_force_values) != expected_atom_count
        or len(oracle_force_values) != len(force_values)
    ):
        reasons.append("oracle_force_array_evidence_invalid")

    evidence_projection = {
        "component_energy_values_and_units": component_rows,
        "component_total_in_evaluator_sum_order": component_total,
        "component_total_matches_retained_total": (
            component_total is not None
            and _is_finite_number(total_energy)
            and component_total.hex() == float(total_energy).hex()
        ),
        "total_energy_value": total_energy,
        "total_energy_unit": variant.get("total_energy_unit"),
        "force_array_shape": shape,
        "force_array_dtype": variant.get("force_array_dtype"),
        "force_array_unit": variant.get("force_array_unit"),
        "force_array_sha256": variant.get("force_array_sha256"),
        "recomputed_force_array_sha256": force_sha256,
        "oracle_total_energy_value": variant.get("oracle_total_energy_value"),
        "oracle_total_energy_unit": variant.get("oracle_total_energy_unit"),
        "oracle_force_array_sha256": variant.get("oracle_force_array_sha256"),
        "recomputed_oracle_force_array_sha256": oracle_force_sha256,
    }
    return {
        **evidence_projection,
        "component_energy_evidence_sha256": _sha256(component_rows),
        "successful_result_evidence_sha256": _sha256(evidence_projection),
    }, reasons


def _flatten_force_values(value: object) -> list[float] | None:
    if not isinstance(value, list) or not value:
        return None
    result: list[float] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 3:
            return None
        for item in row:
            if not _is_finite_number(item):
                return None
            result.append(float(item))
    return result


def _max_abs(first: Sequence[float], second: Sequence[float]) -> float | None:
    if len(first) != len(second) or not first:
        return None
    return max(abs(value - reference) for value, reference in zip(first, second))


def _max_rel(first: Sequence[float], second: Sequence[float]) -> float | None:
    if len(first) != len(second) or not first:
        return None
    return max(
        abs(value - reference) / max(abs(reference), _RELATIVE_ERROR_DENOMINATOR_FLOOR)
        for value, reference in zip(first, second)
    )


def _net_force_norm(variant: Mapping[str, Any]) -> float | None:
    values = variant.get("force_array_values")
    if not isinstance(values, list) or not values:
        return None
    totals = [0.0, 0.0, 0.0]
    for row in values:
        if not isinstance(row, list) or len(row) != 3:
            return None
        for axis, item in enumerate(row):
            if not _is_finite_number(item):
                return None
            totals[axis] += float(item)
    return math.sqrt(sum(value * value for value in totals))


def _recompute_case_metric_values(
    case_id: str,
    variants: Sequence[Mapping[str, Any]],
) -> dict[str, float | bool]:
    """Independently derive every metric from retained raw result evidence."""

    successes = [row for row in variants if row.get("observed_status") == "success"]
    values: dict[str, float | bool] = {}
    if successes:
        energies: list[float] = []
        oracle_energies: list[float] = []
        forces: list[float] = []
        oracle_forces: list[float] = []
        complete = True
        for row in successes:
            energy = row.get("total_energy_value")
            oracle_energy = row.get("oracle_total_energy_value")
            flattened_force = _flatten_force_values(row.get("force_array_values"))
            flattened_oracle_force = _flatten_force_values(
                row.get("oracle_force_array_values")
            )
            if (
                not _is_finite_number(energy)
                or not _is_finite_number(oracle_energy)
                or flattened_force is None
                or flattened_oracle_force is None
                or len(flattened_force) != len(flattened_oracle_force)
            ):
                complete = False
                break
            energies.append(float(energy))
            oracle_energies.append(float(oracle_energy))
            forces.extend(flattened_force)
            oracle_forces.extend(flattened_oracle_force)
        if complete:
            energy_abs = _max_abs(energies, oracle_energies)
            energy_rel = _max_rel(energies, oracle_energies)
            force_abs = _max_abs(forces, oracle_forces)
            force_rel = _max_rel(forces, oracle_forces)
            if None not in {energy_abs, energy_rel, force_abs, force_rel}:
                values.update(
                    {
                        "energy_oracle_max_abs_error": energy_abs,
                        "energy_oracle_max_rel_error": energy_rel,
                        "force_oracle_max_component_abs_error": force_abs,
                        "force_oracle_max_component_rel_error": force_rel,
                    }
                )

    by_id = {row.get("variant_id"): row for row in successes}
    if len(by_id) != len(successes):
        return {}
    if case_id == "quintic_switch_window_and_cutoff" and len(by_id) == 3:
        energy_values = [row.get("total_energy_value") for row in by_id.values()]
        force_values = [
            value
            for row in by_id.values()
            for value in (_flatten_force_values(row.get("force_array_values")) or [])
        ]
        if all(_is_finite_number(value) for value in energy_values) and force_values:
            values["switch_cutoff_energy_abs"] = max(
                abs(float(value)) for value in energy_values
            )
            values["switch_cutoff_force_max_abs"] = max(
                abs(value) for value in force_values
            )
    elif case_id == "orthorhombic_minimum_image" and set(by_id) == {
        "periodic-minimum-image",
        "direct-equivalent",
    }:
        periodic = by_id["periodic-minimum-image"]
        direct = by_id["direct-equivalent"]
        periodic_energy = periodic.get("total_energy_value")
        direct_energy = direct.get("total_energy_value")
        periodic_force = _flatten_force_values(periodic.get("force_array_values"))
        direct_force = _flatten_force_values(direct.get("force_array_values"))
        force_error = (
            _max_abs(periodic_force, direct_force)
            if periodic_force is not None and direct_force is not None
            else None
        )
        if (
            _is_finite_number(periodic_energy)
            and _is_finite_number(direct_energy)
            and force_error is not None
        ):
            values["minimum_image_energy_abs_error"] = abs(
                float(periodic_energy) - float(direct_energy)
            )
            values["minimum_image_force_max_abs_error"] = force_error
    elif case_id == "full_five_term_composition" and by_id:
        norms = [_net_force_norm(row) for row in by_id.values()]
        if norms and all(value is not None for value in norms):
            values["net_force_norm"] = max(float(value) for value in norms)
    elif case_id == "full_force_central_difference" and len(by_id) == 25:
        baseline = by_id.get("baseline")
        baseline_values = (
            baseline.get("force_array_values")
            if isinstance(baseline, Mapping)
            else None
        )
        numerical: list[float] = []
        reference: list[float] = []
        complete = isinstance(baseline_values, list)
        if complete:
            for atom_index, force_row in enumerate(baseline_values):
                if not isinstance(force_row, list) or len(force_row) != 3:
                    complete = False
                    break
                for axis_name, axis in _AXIS_INDEX.items():
                    minus = by_id.get(f"atom-{atom_index}-{axis_name}-minus")
                    plus = by_id.get(f"atom-{atom_index}-{axis_name}-plus")
                    minus_energy = (
                        minus.get("total_energy_value")
                        if isinstance(minus, Mapping)
                        else None
                    )
                    plus_energy = (
                        plus.get("total_energy_value")
                        if isinstance(plus, Mapping)
                        else None
                    )
                    if (
                        not _is_finite_number(minus_energy)
                        or not _is_finite_number(plus_energy)
                        or not _is_finite_number(force_row[axis])
                    ):
                        complete = False
                        break
                    numerical.append(
                        -(float(plus_energy) - float(minus_energy))
                        / (2.0 * _CENTRAL_DIFFERENCE_STEP_ANGSTROM)
                    )
                    reference.append(float(force_row[axis]))
                if not complete:
                    break
        if complete:
            absolute = _max_abs(reference, numerical)
            relative = _max_rel(reference, numerical)
            if absolute is not None and relative is not None:
                values["finite_difference_force_max_abs_error"] = absolute
                values["finite_difference_force_max_rel_error"] = relative
    elif case_id == "rigid_translation_invariance" and set(by_id) == {
        "baseline",
        "translated",
    }:
        baseline = by_id["baseline"]
        translated = by_id["translated"]
        baseline_energy = baseline.get("total_energy_value")
        translated_energy = translated.get("total_energy_value")
        baseline_force = _flatten_force_values(baseline.get("force_array_values"))
        translated_force = _flatten_force_values(translated.get("force_array_values"))
        force_drift = (
            _max_abs(baseline_force, translated_force)
            if baseline_force is not None and translated_force is not None
            else None
        )
        norms = (_net_force_norm(baseline), _net_force_norm(translated))
        if (
            _is_finite_number(baseline_energy)
            and _is_finite_number(translated_energy)
            and force_drift is not None
            and all(value is not None for value in norms)
        ):
            values["translation_energy_abs_drift"] = abs(
                float(baseline_energy) - float(translated_energy)
            )
            values["translation_force_max_abs_drift"] = force_drift
            values["net_force_norm"] = max(float(value) for value in norms)
    elif case_id == "rigid_rotation_invariance" and set(by_id) == {
        "baseline",
        "rotated",
    }:
        baseline = by_id["baseline"]
        rotated = by_id["rotated"]
        baseline_energy = baseline.get("total_energy_value")
        rotated_energy = rotated.get("total_energy_value")
        baseline_force_rows = baseline.get("force_array_values")
        rotated_force = _flatten_force_values(rotated.get("force_array_values"))
        covariant: list[float] = []
        if isinstance(baseline_force_rows, list):
            for row in baseline_force_rows:
                if (
                    not isinstance(row, list)
                    or len(row) != 3
                    or not all(_is_finite_number(value) for value in row)
                ):
                    covariant = []
                    break
                covariant.extend(
                    sum(
                        _ROTATION_MATRIX[axis][column] * float(row[column])
                        for column in range(3)
                    )
                    for axis in range(3)
                )
        covariance_error = (
            _max_abs(rotated_force, covariant)
            if rotated_force is not None and covariant
            else None
        )
        if (
            _is_finite_number(baseline_energy)
            and _is_finite_number(rotated_energy)
            and covariance_error is not None
        ):
            values["rotation_energy_abs_drift"] = abs(
                float(baseline_energy) - float(rotated_energy)
            )
            values["rotation_force_covariance_max_abs_error"] = covariance_error
    elif case_id == "atom_permutation_equivariance" and set(by_id) == {
        "baseline",
        "permuted",
    }:
        baseline = by_id["baseline"]
        permuted = by_id["permuted"]
        baseline_energy = baseline.get("total_energy_value")
        permuted_energy = permuted.get("total_energy_value")
        baseline_force_rows = baseline.get("force_array_values")
        permuted_force = _flatten_force_values(permuted.get("force_array_values"))
        expected: list[float] = []
        if isinstance(baseline_force_rows, list) and len(baseline_force_rows) == 4:
            try:
                expected = [
                    float(value)
                    for old_index in _PERMUTATION_NEW_TO_OLD
                    for value in baseline_force_rows[old_index]
                ]
            except (TypeError, ValueError, IndexError):
                expected = []
        permutation_error = (
            _max_abs(permuted_force, expected)
            if permuted_force is not None and expected
            else None
        )
        if (
            _is_finite_number(baseline_energy)
            and _is_finite_number(permuted_energy)
            and permutation_error is not None
        ):
            values["permutation_energy_abs_drift"] = abs(
                float(baseline_energy) - float(permuted_energy)
            )
            values["permutation_force_equivariance_max_abs_error"] = permutation_error
    elif case_id == "same_environment_repeat_determinism" and set(by_id) == {
        "repeat-1",
        "repeat-2",
        "repeat-3",
    }:
        ordered = [by_id[f"repeat-{index}"] for index in (1, 2, 3)]
        energies = [row.get("total_energy_value") for row in ordered]
        forces = [
            _flatten_force_values(row.get("force_array_values")) for row in ordered
        ]
        if all(_is_finite_number(value) for value in energies) and all(
            value is not None for value in forces
        ):
            values["repeat_energy_bitwise_equal"] = (
                len({float(value).hex() for value in energies}) == 1
            )
            values["repeat_force_bitwise_equal"] = (
                len(
                    {
                        tuple(float(value).hex() for value in force)
                        for force in forces
                        if force is not None
                    }
                )
                == 1
            )
    return values


def _metric_values_equal(retained: object, recomputed: object) -> bool:
    if type(recomputed) is bool:
        return type(retained) is bool and retained is recomputed
    return (
        type(retained) is float
        and type(recomputed) is float
        and math.isfinite(retained)
        and math.isfinite(recomputed)
        and retained.hex() == recomputed.hex()
    )


def _case_review_rows_from_result_receipt(
    result_receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    protocol, materialization = _protocol_and_materialization()
    protocol_cases = protocol["fixture_manifest"]["cases"]
    materialized_cases = materialization["cases"]
    metric_contracts = _metric_contract_map()
    fixture_atom_counts = {
        fixture["spec_id"]: len(fixture["payload"]["atoms"])
        for fixture in protocol["fixture_manifest"]["fixtures"]
    }
    case_results = result_receipt.get("case_results")
    if not isinstance(case_results, list) or len(case_results) != 27:
        raise ReferenceValidationResultReviewError(
            "result receipt must contain exactly twenty-seven case rows"
        )

    rows: list[dict[str, Any]] = []
    for ordinal, (case_result, protocol_case, materialized_case) in enumerate(
        zip(case_results, protocol_cases, materialized_cases, strict=True)
    ):
        if not isinstance(case_result, Mapping):
            raise ReferenceValidationResultReviewError(
                "result receipt case row must be a mapping"
            )
        expected_identity = (
            ordinal,
            protocol_case["case_id"],
            protocol_case["input_sha256"],
            materialized_case["materialization_sha256"],
            protocol_case["expected_outcome"],
            protocol_case["expected_error_code"],
        )
        observed_identity = (
            case_result.get("ordinal"),
            case_result.get("case_id"),
            case_result.get("case_input_sha256"),
            case_result.get("materialization_sha256"),
            case_result.get("expected_outcome"),
            case_result.get("expected_error_code"),
        )
        if observed_identity != expected_identity:
            raise ReferenceValidationResultReviewError(
                "result receipt case identity is omitted, reordered, duplicated, or cross-wired"
            )

        retained_variants = case_result.get("variant_results")
        expected_variants = materialized_case["variants"]
        if not isinstance(retained_variants, list) or len(retained_variants) != len(
            expected_variants
        ):
            raise ReferenceValidationResultReviewError(
                "result receipt variant coverage is incomplete"
            )
        variant_dispositions: list[dict[str, Any]] = []
        failure_dispositions: list[dict[str, Any]] = []
        for variant_ordinal, (variant, expected_variant) in enumerate(
            zip(retained_variants, expected_variants, strict=True)
        ):
            if not isinstance(variant, Mapping):
                raise ReferenceValidationResultReviewError(
                    "result receipt variant row must be a mapping"
                )
            expected_variant_identity = (
                variant_ordinal,
                expected_variant["variant_id"],
                expected_variant["runtime_input_sha256"],
                expected_variant["oracle_input_sha256"],
            )
            observed_variant_identity = (
                variant.get("ordinal"),
                variant.get("variant_id"),
                variant.get("runtime_input_sha256"),
                variant.get("oracle_input_sha256"),
            )
            if observed_variant_identity != expected_variant_identity:
                raise ReferenceValidationResultReviewError(
                    "result receipt variant is omitted, reordered, duplicated, or cross-wired"
                )
            reasons: list[str] = []
            successful_evidence: dict[str, Any] | None = None
            if protocol_case["expected_outcome"] == "pass":
                if variant.get("observed_status") != "success":
                    reasons.append("passing_variant_did_not_succeed")
                if variant.get("observed_error_code") is not None:
                    reasons.append("passing_variant_retained_error_code")
                if variant.get("observed_status") == "success":
                    successful_evidence, evidence_reasons = (
                        _successful_variant_evidence_review(
                            variant,
                            expected_atom_count=fixture_atom_counts[
                                protocol_case["fixture_profile_id"]
                            ],
                        )
                    )
                    reasons.extend(evidence_reasons)
            else:
                if variant.get("observed_status") != "fail_closed":
                    reasons.append("expected_fail_closed_variant_status_mismatch")
                if (
                    variant.get("observed_error_code")
                    != protocol_case["expected_error_code"]
                ):
                    reasons.append("expected_fail_closed_error_code_mismatch")
                numeric_keys = {
                    "component_energy_values_and_units",
                    "total_energy_value",
                    "force_array_values",
                    "oracle_total_energy_value",
                    "oracle_force_array_values",
                }
                if any(key in variant for key in numeric_keys):
                    reasons.append("fail_closed_variant_retained_numeric_evidence")

            disposition = (
                VARIANT_DISPOSITION_ACCEPTED
                if not reasons
                else VARIANT_DISPOSITION_REJECTED
            )
            variant_row = {
                "ordinal": variant_ordinal,
                "variant_id": expected_variant["variant_id"],
                "runtime_input_sha256": expected_variant["runtime_input_sha256"],
                "oracle_input_sha256": expected_variant["oracle_input_sha256"],
                "retained_variant_sha256": _sha256(dict(variant)),
                "retained_observed_status": variant.get("observed_status"),
                "retained_observed_error_code": variant.get("observed_error_code"),
                "successful_result_evidence": successful_evidence,
                "disposition": disposition,
                "rejection_reasons": reasons,
            }
            variant_dispositions.append(variant_row)
            if variant.get("observed_status") != "success":
                failure_dispositions.append(
                    {
                        "variant_ordinal": variant_ordinal,
                        "variant_id": expected_variant["variant_id"],
                        "expected_outcome": protocol_case["expected_outcome"],
                        "expected_error_code": protocol_case["expected_error_code"],
                        "observed_status": variant.get("observed_status"),
                        "observed_error_code": variant.get("observed_error_code"),
                        "disposition": (
                            FAILURE_DISPOSITION_ACCEPTED
                            if protocol_case["expected_outcome"] == "fail_closed"
                            and not reasons
                            else FAILURE_DISPOSITION_REJECTED
                        ),
                        "rejection_reasons": list(reasons),
                    }
                )

        retained_metrics = case_result.get("metric_values")
        required_metric_ids = list(protocol_case["required_metric_ids"])
        if not isinstance(retained_metrics, list) or len(retained_metrics) != len(
            required_metric_ids
        ):
            raise ReferenceValidationResultReviewError(
                "result receipt required metric coverage is incomplete"
            )
        observed_metric_ids = [
            row.get("metric_id") if isinstance(row, Mapping) else None
            for row in retained_metrics
        ]
        if observed_metric_ids != required_metric_ids:
            raise ReferenceValidationResultReviewError(
                "result receipt metric rows are omitted, reordered, duplicated, or unexpected"
            )
        recomputed_metric_values = _recompute_case_metric_values(
            protocol_case["case_id"],
            retained_variants,
        )
        metric_dispositions: list[dict[str, Any]] = []
        for metric_ordinal, (metric, metric_id) in enumerate(
            zip(retained_metrics, required_metric_ids, strict=True)
        ):
            if not isinstance(metric, Mapping):
                raise ReferenceValidationResultReviewError(
                    "result receipt metric row must be a mapping"
                )
            contract = metric_contracts[metric_id]
            structural_identity = (
                metric.get("unit"),
                metric.get("threshold_operator"),
                metric.get("threshold_value"),
            )
            expected_metric_identity = (
                contract["unit"],
                contract["threshold_operator"],
                contract["threshold_value"],
            )
            if structural_identity != expected_metric_identity:
                raise ReferenceValidationResultReviewError(
                    "result receipt metric definition drifted from the frozen protocol"
                )
            value = metric.get("value") if metric.get("observed") is True else None
            recomputed_value = recomputed_metric_values.get(metric_id)
            value_matches_recomputed = (
                metric.get("observed") is True
                and recomputed_value is not None
                and _metric_values_equal(value, recomputed_value)
            )
            recomputed_passed = value_matches_recomputed and _metric_passed(
                contract, recomputed_value
            )
            metric_reasons: list[str] = []
            if not value_matches_recomputed:
                metric_reasons.append(
                    "retained_metric_value_does_not_match_raw_result_evidence"
                )
            if value_matches_recomputed and not recomputed_passed:
                metric_reasons.append("metric_value_did_not_meet_frozen_threshold")
            metric_dispositions.append(
                {
                    "ordinal": metric_ordinal,
                    "metric_id": metric_id,
                    "retained_metric_sha256": _sha256(dict(metric)),
                    "value": value,
                    "recomputed_value": recomputed_value,
                    "retained_value_matches_recomputed": value_matches_recomputed,
                    "observed": metric.get("observed"),
                    "unit": contract["unit"],
                    "threshold_operator": contract["threshold_operator"],
                    "threshold_value": contract["threshold_value"],
                    "retained_passed": metric.get("passed"),
                    "recomputed_passed": recomputed_passed,
                    "disposition": (
                        METRIC_DISPOSITION_ACCEPTED
                        if recomputed_passed
                        else METRIC_DISPOSITION_REJECTED
                    ),
                    "rejection_reasons": metric_reasons,
                }
            )

        metric_ledger_mismatch = any(
            row["retained_value_matches_recomputed"] is not True
            for row in metric_dispositions
        )
        if metric_ledger_mismatch:
            for variant_row in variant_dispositions:
                if variant_row["successful_result_evidence"] is not None:
                    variant_row["disposition"] = VARIANT_DISPOSITION_REJECTED
                    variant_row["rejection_reasons"].append(
                        "variant_raw_evidence_does_not_match_retained_metric_ledger"
                    )

        case_reasons: list[str] = []
        if case_result.get("observation_origin") != "worker":
            case_reasons.append("case_result_not_emitted_by_complete_worker")
        if any(
            row["disposition"] != VARIANT_DISPOSITION_ACCEPTED
            for row in variant_dispositions
        ):
            case_reasons.append("one_or_more_variant_dispositions_rejected")
        if any(
            row["disposition"] != METRIC_DISPOSITION_ACCEPTED
            for row in metric_dispositions
        ):
            case_reasons.append("one_or_more_metric_dispositions_rejected")
        if any(
            row["disposition"] == FAILURE_DISPOSITION_REJECTED
            for row in failure_dispositions
        ):
            case_reasons.append("one_or_more_failure_dispositions_rejected")

        recomputed_status = (
            "metrics_passed"
            if protocol_case["expected_outcome"] == "pass" and not case_reasons
            else (
                "metric_threshold_failed"
                if protocol_case["expected_outcome"] == "pass"
                and all(
                    row["disposition"] == VARIANT_DISPOSITION_ACCEPTED
                    for row in variant_dispositions
                )
                else (
                    "fail_closed_as_expected"
                    if protocol_case["expected_outcome"] == "fail_closed"
                    and not case_reasons
                    else "rejected_observation"
                )
            )
        )
        case_accepted = not case_reasons
        rows.append(
            {
                "ordinal": ordinal,
                "case_id": protocol_case["case_id"],
                "retained_case_sha256": _sha256(dict(case_result)),
                "case_input_sha256": protocol_case["input_sha256"],
                "materialization_sha256": materialized_case["materialization_sha256"],
                "expected_outcome": protocol_case["expected_outcome"],
                "expected_error_code": protocol_case["expected_error_code"],
                "required_metric_ids": required_metric_ids,
                "retained_observation_origin": case_result.get("observation_origin"),
                "retained_observed_status": case_result.get("observed_status"),
                "retained_observed_error_code": case_result.get("observed_error_code"),
                "retained_case_passed": case_result.get("case_passed"),
                "recomputed_observed_status": recomputed_status,
                "recomputed_case_passed": case_accepted,
                "variant_dispositions": variant_dispositions,
                "metric_dispositions": metric_dispositions,
                "failure_dispositions": failure_dispositions,
                "disposition": (
                    CASE_DISPOSITION_ACCEPTED
                    if case_accepted
                    else CASE_DISPOSITION_REJECTED
                ),
                "rejection_reasons": case_reasons,
            }
        )

    if sum(len(row["variant_dispositions"]) for row in rows) != 59:
        raise ReferenceValidationResultReviewError(
            "derived variant disposition coverage drifted"
        )
    if sum(len(row["metric_dispositions"]) for row in rows) != 56:
        raise ReferenceValidationResultReviewError(
            "derived metric disposition occurrence coverage drifted"
        )
    if {
        metric["metric_id"] for row in rows for metric in row["metric_dispositions"]
    } != set(metric_contracts):
        raise ReferenceValidationResultReviewError(
            "derived metric disposition definitions are incomplete"
        )
    return rows


def _frame(
    *,
    frame_type: str,
    worker_kind: str,
    request_sha256: str,
    value: Mapping[str, Any],
    ordinal: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_id": REFERENCE_VALIDATION_WORKER_FRAME_SCHEMA_ID,
        "frame_type": frame_type,
        "worker_kind": worker_kind,
        "worker_request_sha256": request_sha256,
    }
    if frame_type == "payload":
        result["ordinal"] = ordinal
        result["payload"] = dict(value)
    else:
        result["evidence"] = dict(value)
    return result


def _worker_execution_review_row(
    *,
    worker_kind: str,
    result_receipt: Mapping[str, Any],
    payload_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observation = result_receipt["run_observation"]
    lifecycle = observation[f"{worker_kind}_worker_lifecycle_evidence"]
    provenance = observation[f"{worker_kind}_worker_execution_provenance"]
    reasons: list[str] = []

    try:
        request_bytes = bytes.fromhex(provenance["worker_request_canonical_jsonl_hex"])
    except (KeyError, TypeError, ValueError):
        request_bytes = b""
        reasons.append("worker_request_transport_is_not_lowercase_hex")
    request_document: dict[str, Any] | None = None
    if not request_bytes.endswith(b"\n"):
        reasons.append("worker_request_transport_is_not_canonical_jsonl")
    else:
        try:
            loaded = json.loads(request_bytes[:-1].decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if (
            not isinstance(loaded, dict)
            or _canonical_bytes(loaded) + b"\n" != request_bytes
        ):
            reasons.append("worker_request_transport_is_not_canonical_jsonl")
        else:
            request_document = loaded

    request_sha256 = provenance.get("worker_request_sha256")
    if request_document is None:
        recomputed_request_sha256 = None
    else:
        recomputed_request_sha256 = _sha256(request_document)
        expected_dependency_rows = {
            row["artifact_id"]: row["sha256"]
            for row in result_receipt["dependency_artifact_sha256_rows"]
        }
        expected_materialization = (
            None
            if worker_kind == "manifest"
            else reference_validation_materialization_manifest_document()[
                "materialization_manifest_sha256"
            ]
        )
        expected_runner_start = (
            None
            if worker_kind == "manifest"
            else result_receipt["runner_start_record_sha256"]
        )
        expected_request_rows = {
            "schema_id": REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID,
            "worker_kind": worker_kind,
            "expected_protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "expected_materialization_manifest_sha256": expected_materialization,
            "expected_case_count": 27,
            "expected_variant_count": 59,
            "expected_code_commit_sha": result_receipt["code_commit_sha"],
            "expected_runner_source_sha256": result_receipt["runner_source_sha256"],
            "expected_source_manifest_sha256": result_receipt["source_manifest_sha256"],
            "expected_dependency_artifact_sha256_rows": expected_dependency_rows,
            "expected_environment_receipt_sha256": result_receipt[
                "execution_environment_receipt_sha256"
            ],
            "expected_environment_fingerprint_sha256": result_receipt[
                "environment_fingerprint_sha256"
            ],
            "expected_authorization_nonce_sha256": result_receipt[
                "authorization_nonce_sha256"
            ],
            "expected_runner_start_record_sha256": expected_runner_start,
            "expected_application_seed": result_receipt["seed"],
        }
        if any(
            request_document.get(key) != value
            for key, value in expected_request_rows.items()
        ):
            reasons.append("worker_request_is_cross_wired_to_result_receipt")
        environment = request_document.get("expected_worker_environment")
        roots = request_document.get("dependency_roots")
        if (
            not isinstance(environment, dict)
            or not isinstance(roots, list)
            or not roots
            or environment.get("PYTHONPATH") != os.pathsep.join(roots)
            or environment.get("PYTHONHASHSEED")
            != str(request_document.get("expected_python_hash_seed"))
            or environment.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV)
            != str(result_receipt["seed"])
            or request_document.get("expected_worker_environment_sha256")
            != _sha256(environment)
        ):
            reasons.append("worker_request_environment_is_cross_wired")
    if request_sha256 != recomputed_request_sha256:
        reasons.append("worker_request_digest_mismatch")
    if provenance.get("worker_request_byte_count") != len(request_bytes):
        reasons.append("worker_request_byte_count_mismatch")
    if provenance.get("worker_request_transport_sha256") != _raw_sha256(request_bytes):
        reasons.append("worker_request_transport_digest_mismatch")

    completion_state = lifecycle.get("completion_state")
    if (
        completion_state != "complete"
        or provenance.get("completion_state") != "complete"
    ):
        reasons.append("worker_execution_is_incomplete")
    if (
        lifecycle.get("failure_code") is not None
        or provenance.get("failure_code") is not None
    ):
        reasons.append("worker_execution_retained_failure_code")
    if lifecycle.get("worker_request_sha256") != request_sha256:
        reasons.append("worker_lifecycle_request_digest_mismatch")
    lifecycle_projection = {
        key: value for key, value in lifecycle.items() if key != "lifecycle_sha256"
    }
    if lifecycle.get("lifecycle_sha256") != _sha256(lifecycle_projection):
        reasons.append("worker_lifecycle_digest_mismatch")
    if provenance.get("lifecycle_evidence_sha256") != _sha256(lifecycle):
        reasons.append("worker_provenance_lifecycle_digest_mismatch")

    reconstructed = b""
    reconstructed_sequence: list[dict[str, Any]] = []
    if completion_state == "complete" and request_sha256 == recomputed_request_sha256:
        frames = [
            _frame(
                frame_type="pre",
                worker_kind=worker_kind,
                request_sha256=request_sha256,
                value=lifecycle["pre"],
            ),
            *[
                _frame(
                    frame_type="payload",
                    worker_kind=worker_kind,
                    request_sha256=request_sha256,
                    value=row,
                    ordinal=ordinal,
                )
                for ordinal, row in enumerate(payload_rows)
            ],
            _frame(
                frame_type="completion",
                worker_kind=worker_kind,
                request_sha256=request_sha256,
                value=lifecycle,
            ),
        ]
        raw_frames = [_canonical_bytes(frame) + b"\n" for frame in frames]
        reconstructed = b"".join(raw_frames)
        reconstructed_sequence = [
            {
                "frame_index": index,
                "frame_type": frame["frame_type"],
                "ordinal": frame.get("ordinal"),
                "worker_kind": worker_kind,
                "worker_request_sha256": request_sha256,
                "frame_byte_count": len(raw),
                "frame_sha256": _raw_sha256(raw),
            }
            for index, (frame, raw) in enumerate(zip(frames, raw_frames, strict=True))
        ]
        if provenance.get("transcript_sha256") != _raw_sha256(reconstructed):
            reasons.append("worker_transcript_digest_mismatch")
        if provenance.get("transcript_byte_count") != len(reconstructed):
            reasons.append("worker_transcript_byte_count_mismatch")
        if provenance.get("canonical_frame_sequence") != reconstructed_sequence:
            reasons.append("worker_transcript_frame_sequence_mismatch")

    expected_payload_count = 1 if worker_kind == "manifest" else 27
    if (
        len(payload_rows) != expected_payload_count
        or provenance.get("accepted_payload_frame_count") != expected_payload_count
        or provenance.get("parsed_prefix_frame_count") != expected_payload_count + 2
        or provenance.get("canonical_prefix_byte_count")
        != provenance.get("transcript_byte_count")
        or provenance.get("discarded_suffix_byte_count") != 0
        or provenance.get("trailing_fragment_byte_count") != 0
        or provenance.get("discarded_payload_frame_count") != 0
        or provenance.get("failure_stage") is not None
        or provenance.get("child_exit_code") != 0
        or provenance.get("timed_out") is not False
        or provenance.get("output_overflow") is not False
        or provenance.get("communication_failed") is not False
        or provenance.get("request_fully_written") is not True
        or provenance.get("raw_partial_not_independently_replayable") is not False
        or provenance.get("partial_worker_payload_accepted") is not False
    ):
        reasons.append("worker_complete_frame_or_discard_contract_failed")

    process_id = provenance.get("supervisor_launched_child_process_id")
    pre_snapshot = (
        lifecycle.get("pre", {}).get("snapshot", {})
        if isinstance(lifecycle.get("pre"), Mapping)
        else {}
    )
    post_snapshot = (
        lifecycle.get("post", {}).get("snapshot", {})
        if isinstance(lifecycle.get("post"), Mapping)
        else {}
    )
    pid_verified = (
        type(process_id) is int
        and process_id > 0
        and pre_snapshot.get("process_id") == process_id
        and post_snapshot.get("process_id") == process_id
    )
    snapshots_equal = pre_snapshot.get(
        "snapshot_sha256"
    ) is not None and pre_snapshot.get("snapshot_sha256") == post_snapshot.get(
        "snapshot_sha256"
    )
    if not pid_verified:
        reasons.append("worker_supervisor_child_pid_binding_failed")
    if not snapshots_equal:
        reasons.append("worker_native_pre_post_snapshot_equality_failed")

    return {
        "worker_kind": worker_kind,
        "worker_request_sha256": request_sha256,
        "recomputed_worker_request_sha256": recomputed_request_sha256,
        "worker_request_transport_sha256": provenance.get(
            "worker_request_transport_sha256"
        ),
        "worker_request_byte_count": provenance.get("worker_request_byte_count"),
        "completion_state": completion_state,
        "lifecycle_sha256": lifecycle.get("lifecycle_sha256"),
        "provenance_sha256": provenance.get("provenance_sha256"),
        "supervisor_launched_child_process_id": process_id,
        "supervisor_child_pid_matches_native_endpoints": pid_verified,
        "native_pre_post_snapshot_equality_verified": snapshots_equal,
        "payload_frame_count": provenance.get("accepted_payload_frame_count"),
        "transcript_frame_count": provenance.get("parsed_prefix_frame_count"),
        "transcript_sha256": provenance.get("transcript_sha256"),
        "reconstructed_transcript_sha256": (
            _raw_sha256(reconstructed) if reconstructed else None
        ),
        "transcript_byte_count": provenance.get("transcript_byte_count"),
        "reconstructed_transcript_byte_count": (
            len(reconstructed) if reconstructed else None
        ),
        "discarded_suffix_byte_count": provenance.get("discarded_suffix_byte_count"),
        "discarded_payload_frame_count": provenance.get(
            "discarded_payload_frame_count"
        ),
        "canonical_frame_sequence_sha256": _sha256(reconstructed_sequence),
        "disposition": (
            WORKER_EXECUTION_DISPOSITION_ACCEPTED
            if not reasons
            else WORKER_EXECUTION_DISPOSITION_REJECTED
        ),
        "rejection_reasons": reasons,
    }


def _worker_execution_review_from_result_receipt(
    result_receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    manifest = reference_validation_materialization_manifest_document()
    manifest_payload = {
        "ordinal": 0,
        "case_id": "materialization_manifest",
        "materialization_manifest": manifest,
    }
    case_rows = result_receipt["case_results"]
    return [
        _worker_execution_review_row(
            worker_kind="manifest",
            result_receipt=result_receipt,
            payload_rows=[manifest_payload],
        ),
        _worker_execution_review_row(
            worker_kind="case",
            result_receipt=result_receipt,
            payload_rows=case_rows,
        ),
    ]


def _dependency_rows(rows: object) -> list[dict[str, str]]:
    if not isinstance(rows, list) or not rows:
        raise ReferenceValidationResultReviewError(
            "result receipt dependency rows are invalid"
        )
    normalized: list[dict[str, str]] = []
    for row in rows:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"artifact_id", "sha256"}
            or not isinstance(row.get("artifact_id"), str)
            or not row["artifact_id"]
        ):
            raise ReferenceValidationResultReviewError(
                "result receipt dependency row is invalid"
            )
        normalized.append(
            {
                "artifact_id": row["artifact_id"],
                "sha256": _require_sha256(
                    row.get("sha256"), name="result receipt dependency artifact"
                ),
            }
        )
    if normalized != sorted(normalized, key=lambda row: row["artifact_id"]) or len(
        {row["artifact_id"] for row in normalized}
    ) != len(normalized):
        raise ReferenceValidationResultReviewError(
            "result receipt dependency rows are not canonical"
        )
    return normalized


def _result_receipt_binding(result_receipt: Mapping[str, Any]) -> dict[str, Any]:
    validated = _validated_result_receipt_document(result_receipt)
    if validated.get("schema_id") != REFERENCE_VALIDATION_RESULT_RECEIPT_SCHEMA_ID:
        raise ReferenceValidationResultReviewError(
            "result receipt schema is unsupported"
        )
    return {
        "result_receipt_sha256": _require_sha256(
            validated.get("receipt_sha256"), name="result receipt"
        ),
        "protocol_sha256": _require_sha256(
            validated.get("protocol_sha256"), name="result receipt protocol"
        ),
        "h5_applicability_record_sha256": _require_sha256(
            validated.get("h5_applicability_record_sha256"),
            name="result receipt applicability record",
        ),
        "artifact_binding_sha256": _require_sha256(
            validated.get("artifact_binding_sha256"),
            name="result receipt artifact binding",
        ),
        "authorization_contract_sha256": _require_sha256(
            validated.get("authorization_contract_sha256"),
            name="result receipt authorization contract",
        ),
        "authorization_receipt_sha256": _require_sha256(
            validated.get("authorization_receipt_sha256"),
            name="result receipt authorization receipt",
        ),
        "authorization_nonce_sha256": _require_sha256(
            validated.get("authorization_nonce_sha256"),
            name="result receipt authorization nonce",
        ),
        "execution_environment_contract_sha256": _require_sha256(
            validated.get("execution_environment_contract_sha256"),
            name="result receipt environment contract",
        ),
        "execution_environment_receipt_sha256": _require_sha256(
            validated.get("execution_environment_receipt_sha256"),
            name="result receipt environment receipt",
        ),
        "environment_fingerprint_sha256": _require_sha256(
            validated.get("environment_fingerprint_sha256"),
            name="result receipt environment fingerprint",
        ),
        "result_contract_sha256": _require_sha256(
            validated.get("result_contract_sha256"),
            name="result receipt result contract",
        ),
        "result_writer_contract_sha256": _require_sha256(
            validated.get("result_writer_contract_sha256"),
            name="result receipt writer contract",
        ),
        "runner_contract_sha256": _require_sha256(
            validated.get("runner_contract_sha256"),
            name="result receipt runner contract",
        ),
        "runner_start_record_sha256": _require_sha256(
            validated.get("runner_start_record_sha256"),
            name="result receipt runner start",
        ),
        "observation_sha256": _require_sha256(
            validated.get("observation_sha256"),
            name="result receipt observation",
        ),
        "result_receipt_created_at_utc": _format_utc(
            _parse_utc(
                validated.get("receipt_created_at_utc"),
                name="result receipt created_at",
            ),
            name="result receipt created_at",
        ),
        "code_commit_sha": _require_commit_sha(
            validated.get("code_commit_sha"), name="result receipt code commit"
        ),
        "runner_source_sha256": _require_sha256(
            validated.get("runner_source_sha256"),
            name="result receipt runner source",
        ),
        "source_manifest_sha256": _require_sha256(
            validated.get("source_manifest_sha256"),
            name="result receipt source manifest",
        ),
        "dependency_artifact_sha256_rows": _dependency_rows(
            validated.get("dependency_artifact_sha256_rows")
        ),
        "review_attestation_sha256": _require_sha256(
            validated.get("review_attestation_sha256"),
            name="result receipt pre-execution review",
        ),
        "independent_scientific_reviewer_identity_sha256": _require_sha256(
            validated.get("independent_reviewer_identity_sha256"),
            name="result receipt scientific reviewer identity",
        ),
        "worker_execution_review": _worker_execution_review_from_result_receipt(
            validated
        ),
    }


def _verify_frozen_receipt_dependencies(binding: Mapping[str, Any]) -> None:
    expected = {
        "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
        "h5_applicability_record_sha256": FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256,
        "artifact_binding_sha256": FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
        "authorization_contract_sha256": FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
        "execution_environment_contract_sha256": FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
        "result_contract_sha256": FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
        "result_writer_contract_sha256": FROZEN_REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
        "runner_contract_sha256": FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
    }
    if any(binding.get(key) != value for key, value in expected.items()):
        raise ReferenceValidationResultReviewError(
            "result receipt frozen dependency identity drifted"
        )


def _verify_upstream_role_chain(
    *,
    result_receipt: Mapping[str, Any],
    pre_execution_review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_scientific_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    trusted_authorization_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    expected_implementation_author_identity_sha256: str,
    expected_independent_scientific_reviewer_identity_sha256: str,
    expected_authorization_operator_identity_sha256: str,
    revoked_pre_execution_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
) -> None:
    binding = _result_receipt_binding(result_receipt)
    expected_author = _require_sha256(
        expected_implementation_author_identity_sha256,
        name="expected implementation author identity",
    )
    expected_reviewer = _require_sha256(
        expected_independent_scientific_reviewer_identity_sha256,
        name="expected scientific reviewer identity",
    )
    expected_operator = _require_sha256(
        expected_authorization_operator_identity_sha256,
        name="expected authorization operator identity",
    )
    revoked_reviews = _external_sha256_set(
        revoked_pre_execution_review_attestation_sha256s,
        name="revoked pre-execution review attestation",
    )
    revoked_authorizations = _external_sha256_set(
        revoked_authorization_receipt_sha256s,
        name="revoked authorization receipt",
    )
    try:
        authorization = verify_signed_reference_validation_authorization_receipt(
            authorization_receipt,
            review_attestation=pre_execution_review_attestation,
            trusted_reviewer_keys=trusted_scientific_reviewer_keys,
            expected_implementation_author_identity_sha256=expected_author,
            trusted_operator_keys=trusted_authorization_operator_keys,
            checked_at=_parse_utc(
                binding["result_receipt_created_at_utc"],
                name="result receipt created_at",
            ),
            expected_code_commit_sha=binding["code_commit_sha"],
            expected_runner_source_sha256=binding["runner_source_sha256"],
            expected_execution_environment_contract_sha256=binding[
                "execution_environment_contract_sha256"
            ],
            expected_result_receipt_contract_sha256=binding["result_contract_sha256"],
            expected_dependency_artifact_sha256_rows={
                row["artifact_id"]: row["sha256"]
                for row in binding["dependency_artifact_sha256_rows"]
            },
            revoked_receipt_sha256s=tuple(sorted(revoked_authorizations)),
            revoked_review_attestation_sha256s=tuple(sorted(revoked_reviews)),
            consumed_nonce_sha256s=(),
        )
    except ReferenceValidationAuthorizationError as exc:
        raise ReferenceValidationResultReviewError(
            "result review upstream signed HMAC chain verification failed"
        ) from exc
    expected_rows = {
        "receipt_sha256": binding["authorization_receipt_sha256"],
        "review_attestation_sha256": binding["review_attestation_sha256"],
        "implementation_author_identity_sha256": expected_author,
        "independent_reviewer_identity_sha256": expected_reviewer,
        "authorization_operator_identity_sha256": expected_operator,
        "authorization_nonce_sha256": binding["authorization_nonce_sha256"],
        "code_commit_sha": binding["code_commit_sha"],
        "runner_source_sha256": binding["runner_source_sha256"],
        "execution_environment_contract_sha256": binding[
            "execution_environment_contract_sha256"
        ],
        "result_receipt_contract_sha256": binding["result_contract_sha256"],
        "dependency_artifact_sha256_rows": tuple(
            (row["artifact_id"], row["sha256"])
            for row in binding["dependency_artifact_sha256_rows"]
        ),
    }
    if any(
        getattr(authorization, field_name) != expected_value
        for field_name, expected_value in expected_rows.items()
    ):
        raise ReferenceValidationResultReviewError(
            "result review upstream HMAC roles or identities are cross-wired"
        )


def _result_review_outcome(
    case_rows: Sequence[Mapping[str, Any]],
    worker_rows: Sequence[Mapping[str, Any]],
) -> str:
    accepted = (
        len(case_rows) == 27
        and sum(row["expected_outcome"] == "pass" for row in case_rows) == 15
        and sum(row["expected_outcome"] == "fail_closed" for row in case_rows) == 12
        and all(
            row.get("disposition") == CASE_DISPOSITION_ACCEPTED for row in case_rows
        )
        and len(worker_rows) == 2
        and all(
            row.get("disposition") == WORKER_EXECUTION_DISPOSITION_ACCEPTED
            for row in worker_rows
        )
    )
    return (
        RESULT_REVIEW_OUTCOME_ACCEPTED if accepted else RESULT_REVIEW_OUTCOME_REJECTED
    )


def _contract_projection() -> dict[str, Any]:
    protocol, materialization = _protocol_and_materialization()
    metrics = protocol["numerical_protocol"]["metrics"]
    cases = protocol["fixture_manifest"]["cases"]
    return {
        "schema_id": REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "scope": "independent_post_result_review_of_one_exact_energy_force_receipt",
            "contract_definition_only": True,
            "result_review_attestation_bundled": False,
            "synthetic_implementation_mathematics_only": True,
            "authorizes_scientific_validation": False,
            "authorizes_parameter_fitting": False,
            "authorizes_product_promotion": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "h5_applicability_record_sha256": FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256,
            "artifact_binding_sha256": FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
            "pre_execution_review_contract_sha256": FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
            "authorization_contract_sha256": FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
            "execution_environment_contract_sha256": FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
            "result_receipt_contract_sha256": FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
            "result_writer_contract_sha256": FROZEN_REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
            "runner_contract_sha256": FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
            "materialization_manifest_sha256": materialization[
                "materialization_manifest_sha256"
            ],
            "exact_result_receipt_self_hash_and_out_of_band_hash_required": True,
            "full_current_writer_receipt_validation_required": True,
            "raw_upstream_signed_review_and_authorization_required": True,
            "upstream_signature_algorithm": "hmac-sha256",
            "leaf_result_review_signature_algorithm": "ed25519",
            "full_asymmetric_chain_claimed": False,
            "independent_live_dependency_manifest_reverification_performed": False,
            "external_worker_launch_authenticity_or_custody_established": False,
            "worker_process_starttime_and_boot_id_bound": False,
        },
        "coverage": {
            "case_count": 27,
            "variant_count": 59,
            "metric_definition_count": 19,
            "required_metric_occurrence_count": 56,
            "expected_pass_case_count": 15,
            "expected_fail_closed_case_count": 12,
            "ordered_case_ids": [case["case_id"] for case in cases],
            "expected_fail_closed_error_codes": [
                case["expected_error_code"]
                for case in cases
                if case["expected_outcome"] == "fail_closed"
            ],
            "metric_definitions": metrics,
            "structural_omission_reorder_or_duplicate_is_validation_error": True,
            "complete_bad_science_is_cryptographically_signable_as_rejected": True,
            "incomplete_worker_evidence_is_cryptographically_signable_as_rejected": True,
        },
        "derivation_policy": {
            "caller_supplied_case_variant_metric_or_failure_dispositions_accepted": False,
            "caller_supplied_outcome_accepted": False,
            "metric_pass_flags_trusted": False,
            "all_metric_values_recomputed_from_retained_raw_energy_and_force_arrays": True,
            "retained_and_recomputed_float_metric_values_must_be_bitwise_equal": True,
            "metric_values_must_be_finite_and_units_operators_thresholds_exact": True,
            "successful_force_array_atom_count_derived_from_frozen_fixture": True,
            "component_energy_names_must_match_exact_five_term_evaluator_set": True,
            "component_energy_total_must_match_evaluator_order_sum_bitwise": True,
            "successful_variant_input_component_total_and_force_evidence_bound": True,
            "all_failure_rows_receive_explicit_dispositions": True,
            "manifest_and_case_worker_requests_reparsed": True,
            "manifest_and_case_transcripts_reconstructed": True,
            "frame_order_count_hash_and_zero_discard_required_for_acceptance": True,
            "supervisor_child_pid_must_match_native_pre_and_post": True,
            "native_pre_post_snapshot_equality_required_for_acceptance": True,
            "incomplete_worker_evidence_eligible_for_acceptance": False,
        },
        "metric_recomputation_constants": {
            "component_energy_names_sorted": list(_COMPONENT_ENERGY_NAMES_SORTED),
            "component_total_sum_order": list(_COMPONENT_TOTAL_SUM_ORDER),
            "central_difference_step_angstrom": _CENTRAL_DIFFERENCE_STEP_ANGSTROM,
            "relative_error_denominator_floor": _RELATIVE_ERROR_DENOMINATOR_FLOOR,
            "rotation_matrix": [list(row) for row in _ROTATION_MATRIX],
            "permutation_new_to_old": list(_PERMUTATION_NEW_TO_OLD),
            "axis_order": ["x", "y", "z"],
        },
        "identity_policy": {
            "implementation_author_identity_required": True,
            "independent_scientific_reviewer_identity_required": True,
            "authorization_operator_identity_required": True,
            "independent_result_reviewer_identity_required": True,
            "all_four_roles_pairwise_distinct": True,
            "result_reviewer_public_key_supplied_out_of_band": True,
            "repository_bundles_trusted_result_reviewer_key": False,
        },
        "attestation_schema": {
            "schema_id": REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
            "signature_algorithm": REFERENCE_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM,
            "maximum_validity_seconds": int(
                REFERENCE_VALIDATION_RESULT_REVIEW_MAX_VALIDITY.total_seconds()
            ),
            "required_check_ids": list(_REQUIRED_RESULT_REVIEW_CHECK_IDS),
            "required_limitation_ids": list(_REQUIRED_LIMITATION_IDS),
            "review_outcomes": [
                RESULT_REVIEW_OUTCOME_ACCEPTED,
                RESULT_REVIEW_OUTCOME_REJECTED,
            ],
            "all_dispositions_and_outcome_derived_from_validated_receipt": True,
            "all_scientific_fitting_benchmark_product_claims_false": True,
        },
        "claim_policy": {
            "production_validation_evidence": False,
            "force_or_energy_validated": False,
            "scientifically_validated": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


def reference_validation_result_review_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
    ):
        raise ReferenceValidationResultReviewError(
            "frozen energy/force result-review contract SHA-256 drifted"
        )
    return document


def require_reference_validation_result_review_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationResultReviewError(
            "result-review contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_validation_result_review_contract_document()
    if observed != expected:
        raise ReferenceValidationResultReviewError(
            "result-review contract document does not match the frozen record"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceValidationResultReviewerTrustAnchor:
    """Out-of-band result-reviewer identity and raw Ed25519 public key."""

    result_reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "result_reviewer_identity_sha256",
            _require_sha256(
                self.result_reviewer_identity_sha256,
                name="trusted result reviewer identity",
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_key(
                self.verification_key,
                name="trusted result reviewer verification key",
            ),
        )


# Short lane-local alias for callers that follow the older minimization name.
ResultReviewerTrustAnchor = ReferenceValidationResultReviewerTrustAnchor


@dataclass(frozen=True, slots=True)
class ReferenceValidationResultReviewVerification:
    contract_sha256: str
    result_receipt_sha256: str
    source_manifest_sha256: str
    attestation_sha256: str
    implementation_author_identity_sha256: str
    independent_scientific_reviewer_identity_sha256: str
    authorization_operator_identity_sha256: str
    independent_result_reviewer_identity_sha256: str
    result_reviewer_key_id: str
    reviewed_at_utc: str
    expires_at_utc: str
    independent_result_review_verified: bool
    implementation_author_separation_verified: bool
    result_receipt_review_outcome: str
    result_receipt_accepted: bool
    production_validation_evidence: bool
    force_or_energy_validated: bool
    scientifically_validated: bool
    parameter_fitting_proposal_authorized: bool
    parameter_fitting_authorized: bool
    benchmark_validated: bool
    product_qualified: bool
    claim_safe: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("contract", self.contract_sha256),
            ("result receipt", self.result_receipt_sha256),
            ("source manifest", self.source_manifest_sha256),
            ("attestation", self.attestation_sha256),
            ("implementation author", self.implementation_author_identity_sha256),
            (
                "scientific reviewer",
                self.independent_scientific_reviewer_identity_sha256,
            ),
            ("authorization operator", self.authorization_operator_identity_sha256),
            ("result reviewer", self.independent_result_reviewer_identity_sha256),
        ):
            _require_sha256(value, name=name)
        if (
            len(
                {
                    self.implementation_author_identity_sha256,
                    self.independent_scientific_reviewer_identity_sha256,
                    self.authorization_operator_identity_sha256,
                    self.independent_result_reviewer_identity_sha256,
                }
            )
            != 4
        ):
            raise ReferenceValidationResultReviewError(
                "verified result-review roles must be pairwise distinct"
            )
        _require_key_id(self.result_reviewer_key_id)
        if _parse_utc(self.expires_at_utc, name="expires_at") <= _parse_utc(
            self.reviewed_at_utc, name="reviewed_at"
        ):
            raise ReferenceValidationResultReviewError(
                "verified result-review expiry must follow review time"
            )
        if (
            not self.independent_result_review_verified
            or not self.implementation_author_separation_verified
        ):
            raise ReferenceValidationResultReviewError(
                "verified result review must retain verification and role separation"
            )
        if self.result_receipt_review_outcome not in {
            RESULT_REVIEW_OUTCOME_ACCEPTED,
            RESULT_REVIEW_OUTCOME_REJECTED,
        } or self.result_receipt_accepted is not (
            self.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED
        ):
            raise ReferenceValidationResultReviewError(
                "verified result-review acceptance contradicts its outcome"
            )
        if any(
            (
                self.production_validation_evidence,
                self.force_or_energy_validated,
                self.scientifically_validated,
                self.parameter_fitting_proposal_authorized,
                self.parameter_fitting_authorized,
                self.benchmark_validated,
                self.product_qualified,
                self.claim_safe,
            )
        ):
            raise ReferenceValidationResultReviewError(
                "result review cannot promote scientific, fitting, benchmark, or product claims"
            )
        if not self.blockers:
            raise ReferenceValidationResultReviewError(
                "verified result review must retain downstream blockers"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_sha256": self.contract_sha256,
            "result_receipt_sha256": self.result_receipt_sha256,
            "source_manifest_sha256": self.source_manifest_sha256,
            "attestation_sha256": self.attestation_sha256,
            "implementation_author_identity_sha256": self.implementation_author_identity_sha256,
            "independent_scientific_reviewer_identity_sha256": self.independent_scientific_reviewer_identity_sha256,
            "authorization_operator_identity_sha256": self.authorization_operator_identity_sha256,
            "independent_result_reviewer_identity_sha256": self.independent_result_reviewer_identity_sha256,
            "result_reviewer_key_id": self.result_reviewer_key_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "independent_result_review_verified": self.independent_result_review_verified,
            "implementation_author_separation_verified": self.implementation_author_separation_verified,
            "result_receipt_review_outcome": self.result_receipt_review_outcome,
            "result_receipt_accepted": self.result_receipt_accepted,
            "production_validation_evidence": self.production_validation_evidence,
            "force_or_energy_validated": self.force_or_energy_validated,
            "scientifically_validated": self.scientifically_validated,
            "parameter_fitting_proposal_authorized": self.parameter_fitting_proposal_authorized,
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "benchmark_validated": self.benchmark_validated,
            "product_qualified": self.product_qualified,
            "claim_safe": self.claim_safe,
            "blockers": list(self.blockers),
        }


def _attestation_projection(
    *,
    result_receipt: Mapping[str, Any],
    implementation_author_identity_sha256: str,
    independent_scientific_reviewer_identity_sha256: str,
    authorization_operator_identity_sha256: str,
    independent_result_reviewer_identity_sha256: str,
    result_reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    nonce_sha256: str,
    accepted_check_ids: Sequence[str],
    acknowledged_limitation_ids: Sequence[str],
) -> dict[str, Any]:
    binding = _result_receipt_binding(result_receipt)
    _verify_frozen_receipt_dependencies(binding)
    author = _require_sha256(
        implementation_author_identity_sha256,
        name="implementation author identity",
    )
    scientific_reviewer = _require_sha256(
        independent_scientific_reviewer_identity_sha256,
        name="independent scientific reviewer identity",
    )
    operator = _require_sha256(
        authorization_operator_identity_sha256,
        name="authorization operator identity",
    )
    result_reviewer = _require_sha256(
        independent_result_reviewer_identity_sha256,
        name="independent result reviewer identity",
    )
    if (
        scientific_reviewer
        != binding["independent_scientific_reviewer_identity_sha256"]
    ):
        raise ReferenceValidationResultReviewError(
            "scientific reviewer identity is cross-wired to the result receipt"
        )
    if len({author, scientific_reviewer, operator, result_reviewer}) != 4:
        raise ReferenceValidationResultReviewError(
            "result-review roles must be pairwise distinct"
        )
    if list(accepted_check_ids) != list(_REQUIRED_RESULT_REVIEW_CHECK_IDS):
        raise ReferenceValidationResultReviewError(
            "result-review check coverage is incomplete or reordered"
        )
    if list(acknowledged_limitation_ids) != list(_REQUIRED_LIMITATION_IDS):
        raise ReferenceValidationResultReviewError(
            "result-review limitations are incomplete or reordered"
        )
    case_rows = _case_review_rows_from_result_receipt(result_receipt)
    outcome = _result_review_outcome(case_rows, binding["worker_execution_review"])
    return {
        "schema_id": REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
        "contract_sha256": reference_validation_result_review_contract_document()[
            "contract_sha256"
        ],
        **binding,
        "implementation_author_identity_sha256": author,
        "independent_scientific_reviewer_identity_sha256": scientific_reviewer,
        "authorization_operator_identity_sha256": operator,
        "independent_result_reviewer_identity_sha256": result_reviewer,
        "result_reviewer_key_id": _require_key_id(result_reviewer_key_id),
        "reviewed_at_utc": reviewed_at_utc,
        "expires_at_utc": expires_at_utc,
        "nonce_sha256": _require_sha256(nonce_sha256, name="result-review nonce"),
        "accepted_check_ids": list(accepted_check_ids),
        "acknowledged_limitation_ids": list(acknowledged_limitation_ids),
        "case_review_rows": case_rows,
        "result_receipt_review_outcome": outcome,
        "result_receipt_accepted": outcome == RESULT_REVIEW_OUTCOME_ACCEPTED,
        "production_validation_evidence": False,
        "force_or_energy_validated": False,
        "scientific_validation_recommended": False,
        "parameter_fitting_proposal_recommended": False,
        "parameter_fitting_recommended": False,
        "scientifically_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }


def build_signed_reference_validation_result_review_attestation(
    *,
    result_receipt: Mapping[str, Any],
    expected_result_receipt_sha256: str,
    pre_execution_review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_scientific_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    trusted_authorization_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    implementation_author_identity_sha256: str,
    independent_scientific_reviewer_identity_sha256: str,
    authorization_operator_identity_sha256: str,
    independent_result_reviewer_identity_sha256: str,
    result_reviewer_key_id: str,
    signing_key: bytes | str,
    reviewed_at: datetime,
    expires_at: datetime,
    nonce_sha256: str,
    revoked_pre_execution_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
    revoked_execution_environment_receipt_sha256s: Sequence[str],
    revoked_result_receipt_sha256s: Sequence[str],
    superseded_result_receipt_sha256s: Sequence[str],
    accepted_check_ids: Sequence[str] = _REQUIRED_RESULT_REVIEW_CHECK_IDS,
    acknowledged_limitation_ids: Sequence[str] = _REQUIRED_LIMITATION_IDS,
    case_review_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive every disposition, bind one exact receipt, and sign the review."""

    if case_review_rows is not None:
        raise ReferenceValidationResultReviewError(
            "caller-supplied result dispositions are not accepted"
        )
    validated = _validated_result_receipt_document(result_receipt)
    binding = _result_receipt_binding(validated)
    expected_receipt = _require_sha256(
        expected_result_receipt_sha256, name="expected result receipt"
    )
    if binding["result_receipt_sha256"] != expected_receipt:
        raise ReferenceValidationResultReviewError(
            "result receipt identity is cross-wired"
        )
    _verify_frozen_receipt_dependencies(binding)
    role_identities = {
        _require_sha256(
            implementation_author_identity_sha256,
            name="implementation author identity",
        ),
        _require_sha256(
            independent_scientific_reviewer_identity_sha256,
            name="independent scientific reviewer identity",
        ),
        _require_sha256(
            authorization_operator_identity_sha256,
            name="authorization operator identity",
        ),
        _require_sha256(
            independent_result_reviewer_identity_sha256,
            name="independent result reviewer identity",
        ),
    }
    if len(role_identities) != 4:
        raise ReferenceValidationResultReviewError(
            "result-review roles must be pairwise distinct"
        )
    _verify_upstream_role_chain(
        result_receipt=validated,
        pre_execution_review_attestation=pre_execution_review_attestation,
        authorization_receipt=authorization_receipt,
        trusted_scientific_reviewer_keys=trusted_scientific_reviewer_keys,
        trusted_authorization_operator_keys=trusted_authorization_operator_keys,
        expected_implementation_author_identity_sha256=(
            implementation_author_identity_sha256
        ),
        expected_independent_scientific_reviewer_identity_sha256=(
            independent_scientific_reviewer_identity_sha256
        ),
        expected_authorization_operator_identity_sha256=(
            authorization_operator_identity_sha256
        ),
        revoked_pre_execution_review_attestation_sha256s=(
            revoked_pre_execution_review_attestation_sha256s
        ),
        revoked_authorization_receipt_sha256s=(revoked_authorization_receipt_sha256s),
    )
    revoked_environments = _external_sha256_set(
        revoked_execution_environment_receipt_sha256s,
        name="revoked execution environment receipt",
    )
    revoked_results = _external_sha256_set(
        revoked_result_receipt_sha256s, name="revoked result receipt"
    )
    superseded_results = _external_sha256_set(
        superseded_result_receipt_sha256s, name="superseded result receipt"
    )
    if binding["execution_environment_receipt_sha256"] in revoked_environments:
        raise ReferenceValidationResultReviewError(
            "execution environment receipt is externally revoked"
        )
    if expected_receipt in revoked_results:
        raise ReferenceValidationResultReviewError(
            "result receipt is externally revoked"
        )
    if expected_receipt in superseded_results:
        raise ReferenceValidationResultReviewError(
            "result receipt is externally superseded"
        )
    reviewed_at_utc = _format_utc(reviewed_at, name="reviewed_at")
    expires_at_utc = _format_utc(expires_at, name="expires_at")
    reviewed_time = _parse_utc(reviewed_at_utc, name="reviewed_at")
    expires_time = _parse_utc(expires_at_utc, name="expires_at")
    if expires_time <= reviewed_time:
        raise ReferenceValidationResultReviewError(
            "result-review expiry must follow review time"
        )
    if expires_time - reviewed_time > REFERENCE_VALIDATION_RESULT_REVIEW_MAX_VALIDITY:
        raise ReferenceValidationResultReviewError(
            "result-review validity exceeds the frozen maximum"
        )
    if reviewed_time < _parse_utc(
        binding["result_receipt_created_at_utc"], name="result receipt created_at"
    ):
        raise ReferenceValidationResultReviewError(
            "result review predates the result receipt"
        )
    projection = _attestation_projection(
        result_receipt=validated,
        implementation_author_identity_sha256=(implementation_author_identity_sha256),
        independent_scientific_reviewer_identity_sha256=(
            independent_scientific_reviewer_identity_sha256
        ),
        authorization_operator_identity_sha256=(authorization_operator_identity_sha256),
        independent_result_reviewer_identity_sha256=(
            independent_result_reviewer_identity_sha256
        ),
        result_reviewer_key_id=result_reviewer_key_id,
        reviewed_at_utc=reviewed_at_utc,
        expires_at_utc=expires_at_utc,
        nonce_sha256=nonce_sha256,
        accepted_check_ids=accepted_check_ids,
        acknowledged_limitation_ids=acknowledged_limitation_ids,
    )
    payload = dict(projection)
    payload["attestation_sha256"] = _sha256(projection)
    try:
        signature = sign_ed25519(
            _canonical_bytes(payload),
            _require_key(signing_key, name="result-review signing key"),
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceValidationResultReviewError(
            "result-review Ed25519 signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": REFERENCE_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(result_reviewer_key_id),
        "value": signature,
    }
    return payload


def _load_attestation(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes):
        raise ReferenceValidationResultReviewError(
            "result-review attestation must be a mapping, string, or bytes"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationResultReviewError(
                    "result-review attestation contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationResultReviewError(
            "result-review attestation must be UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict) or _canonical_bytes(loaded) != raw:
        raise ReferenceValidationResultReviewError(
            "result-review attestation transport is not canonical JSON"
        )
    return loaded


def verify_signed_reference_validation_result_review_attestation(
    source: str | bytes | Mapping[str, Any],
    *,
    result_receipt: Mapping[str, Any],
    pre_execution_review_attestation: str | bytes | Mapping[str, Any],
    authorization_receipt: str | bytes | Mapping[str, Any],
    trusted_scientific_reviewer_keys: Mapping[str, ScientificReviewerTrustAnchor],
    trusted_authorization_operator_keys: Mapping[str, AuthorizationOperatorTrustAnchor],
    expected_result_receipt_sha256: str,
    trusted_result_reviewer_keys: Mapping[
        str, ReferenceValidationResultReviewerTrustAnchor
    ],
    expected_implementation_author_identity_sha256: str,
    expected_independent_scientific_reviewer_identity_sha256: str,
    expected_authorization_operator_identity_sha256: str,
    checked_at: datetime,
    revoked_pre_execution_review_attestation_sha256s: Sequence[str],
    revoked_authorization_receipt_sha256s: Sequence[str],
    revoked_execution_environment_receipt_sha256s: Sequence[str],
    revoked_result_receipt_sha256s: Sequence[str],
    superseded_result_receipt_sha256s: Sequence[str],
    revoked_result_review_attestation_sha256s: Sequence[str],
    superseded_result_review_attestation_sha256s: Sequence[str],
) -> ReferenceValidationResultReviewVerification:
    """Verify the exact receipt, upstream HMAC chain, and Ed25519 leaf review."""

    validated = _validated_result_receipt_document(result_receipt)
    binding = _result_receipt_binding(validated)
    expected_receipt = _require_sha256(
        expected_result_receipt_sha256, name="expected result receipt"
    )
    if binding["result_receipt_sha256"] != expected_receipt:
        raise ReferenceValidationResultReviewError(
            "result receipt identity is cross-wired"
        )
    _verify_frozen_receipt_dependencies(binding)
    expected_author = _require_sha256(
        expected_implementation_author_identity_sha256,
        name="expected implementation author identity",
    )
    expected_scientific_reviewer = _require_sha256(
        expected_independent_scientific_reviewer_identity_sha256,
        name="expected scientific reviewer identity",
    )
    expected_operator = _require_sha256(
        expected_authorization_operator_identity_sha256,
        name="expected authorization operator identity",
    )
    revoked_reviews = _external_sha256_set(
        revoked_pre_execution_review_attestation_sha256s,
        name="revoked pre-execution review attestation",
    )
    revoked_authorizations = _external_sha256_set(
        revoked_authorization_receipt_sha256s,
        name="revoked authorization receipt",
    )
    revoked_environments = _external_sha256_set(
        revoked_execution_environment_receipt_sha256s,
        name="revoked execution environment receipt",
    )
    revoked_results = _external_sha256_set(
        revoked_result_receipt_sha256s, name="revoked result receipt"
    )
    superseded_results = _external_sha256_set(
        superseded_result_receipt_sha256s, name="superseded result receipt"
    )
    revoked_result_reviews = _external_sha256_set(
        revoked_result_review_attestation_sha256s,
        name="revoked result-review attestation",
    )
    superseded_result_reviews = _external_sha256_set(
        superseded_result_review_attestation_sha256s,
        name="superseded result-review attestation",
    )
    if binding["review_attestation_sha256"] in revoked_reviews:
        raise ReferenceValidationResultReviewError(
            "pre-execution review attestation is externally revoked"
        )
    if binding["authorization_receipt_sha256"] in revoked_authorizations:
        raise ReferenceValidationResultReviewError(
            "authorization receipt is externally revoked"
        )
    if binding["execution_environment_receipt_sha256"] in revoked_environments:
        raise ReferenceValidationResultReviewError(
            "execution environment receipt is externally revoked"
        )
    if expected_receipt in revoked_results:
        raise ReferenceValidationResultReviewError(
            "result receipt is externally revoked"
        )
    if expected_receipt in superseded_results:
        raise ReferenceValidationResultReviewError(
            "result receipt is externally superseded"
        )
    _verify_upstream_role_chain(
        result_receipt=validated,
        pre_execution_review_attestation=pre_execution_review_attestation,
        authorization_receipt=authorization_receipt,
        trusted_scientific_reviewer_keys=trusted_scientific_reviewer_keys,
        trusted_authorization_operator_keys=trusted_authorization_operator_keys,
        expected_implementation_author_identity_sha256=expected_author,
        expected_independent_scientific_reviewer_identity_sha256=(
            expected_scientific_reviewer
        ),
        expected_authorization_operator_identity_sha256=expected_operator,
        revoked_pre_execution_review_attestation_sha256s=tuple(sorted(revoked_reviews)),
        revoked_authorization_receipt_sha256s=tuple(sorted(revoked_authorizations)),
    )

    payload = _load_attestation(source)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping) or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ReferenceValidationResultReviewError(
            "result-review attestation signature fields are invalid"
        )
    if (
        signature.get("algorithm")
        != REFERENCE_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM
    ):
        raise ReferenceValidationResultReviewError(
            "result-review signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"))
    anchor = trusted_result_reviewer_keys.get(key_id)
    if not isinstance(anchor, ReferenceValidationResultReviewerTrustAnchor):
        raise ReferenceValidationResultReviewError(
            "result reviewer key id is not trusted"
        )
    try:
        verified_signature = verify_ed25519(
            _canonical_bytes(payload), signature.get("value"), anchor.verification_key
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ReferenceValidationResultReviewError(
            "result-review Ed25519 verifier is unavailable"
        ) from exc
    if not verified_signature:
        raise ReferenceValidationResultReviewError(
            "result-review signature verification failed"
        )
    attestation_sha256 = payload.pop("attestation_sha256", None)
    if attestation_sha256 != _sha256(payload):
        raise ReferenceValidationResultReviewError(
            "result-review attestation SHA-256 verification failed"
        )
    attestation_sha256 = _require_sha256(
        attestation_sha256, name="result-review attestation"
    )
    if attestation_sha256 in revoked_result_reviews:
        raise ReferenceValidationResultReviewError(
            "result-review attestation is externally revoked"
        )
    if attestation_sha256 in superseded_result_reviews:
        raise ReferenceValidationResultReviewError(
            "result-review attestation is externally superseded"
        )
    if (
        payload.get("schema_id")
        != REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID
    ):
        raise ReferenceValidationResultReviewError(
            "result-review attestation schema is unsupported"
        )
    if (
        payload.get("contract_sha256")
        != reference_validation_result_review_contract_document()["contract_sha256"]
    ):
        raise ReferenceValidationResultReviewError(
            "result-review contract identity drifted"
        )
    for key, value in binding.items():
        if payload.get(key) != value:
            raise ReferenceValidationResultReviewError(
                "result-review receipt binding drifted"
            )
    if payload.get("result_receipt_sha256") != expected_receipt:
        raise ReferenceValidationResultReviewError(
            "result-review receipt identity drifted"
        )
    if payload.get("implementation_author_identity_sha256") != expected_author:
        raise ReferenceValidationResultReviewError(
            "result-review implementation author identity drifted"
        )
    if (
        payload.get("independent_scientific_reviewer_identity_sha256")
        != expected_scientific_reviewer
    ):
        raise ReferenceValidationResultReviewError(
            "result-review scientific reviewer identity drifted"
        )
    if payload.get("authorization_operator_identity_sha256") != expected_operator:
        raise ReferenceValidationResultReviewError(
            "result-review authorization operator identity drifted"
        )
    result_reviewer = _require_sha256(
        payload.get("independent_result_reviewer_identity_sha256"),
        name="independent result reviewer identity",
    )
    if result_reviewer != anchor.result_reviewer_identity_sha256:
        raise ReferenceValidationResultReviewError(
            "result reviewer identity does not match the trusted key"
        )
    if (
        len(
            {
                expected_author,
                expected_scientific_reviewer,
                expected_operator,
                result_reviewer,
            }
        )
        != 4
    ):
        raise ReferenceValidationResultReviewError(
            "result-review roles must be pairwise distinct"
        )
    if payload.get("result_reviewer_key_id") != key_id:
        raise ReferenceValidationResultReviewError(
            "result reviewer key id is cross-wired"
        )

    reviewed_at = _parse_utc(payload.get("reviewed_at_utc"), name="reviewed_at")
    expires_at = _parse_utc(payload.get("expires_at_utc"), name="expires_at")
    checked_at_utc = _parse_utc(
        _format_utc(checked_at, name="checked_at"), name="checked_at"
    )
    receipt_created_at = _parse_utc(
        binding["result_receipt_created_at_utc"], name="result receipt created_at"
    )
    if reviewed_at < receipt_created_at:
        raise ReferenceValidationResultReviewError(
            "result review predates the result receipt"
        )
    if (
        expires_at <= reviewed_at
        or expires_at - reviewed_at > REFERENCE_VALIDATION_RESULT_REVIEW_MAX_VALIDITY
    ):
        raise ReferenceValidationResultReviewError(
            "result-review validity interval is invalid"
        )
    if checked_at_utc < reviewed_at:
        raise ReferenceValidationResultReviewError(
            "result-review attestation is not yet valid"
        )
    if checked_at_utc >= expires_at:
        raise ReferenceValidationResultReviewError(
            "result-review attestation is expired"
        )
    if payload.get("accepted_check_ids") != list(_REQUIRED_RESULT_REVIEW_CHECK_IDS):
        raise ReferenceValidationResultReviewError(
            "result-review check coverage is incomplete or reordered"
        )
    if payload.get("acknowledged_limitation_ids") != list(_REQUIRED_LIMITATION_IDS):
        raise ReferenceValidationResultReviewError(
            "result-review limitations are incomplete or reordered"
        )

    expected_projection = _attestation_projection(
        result_receipt=validated,
        implementation_author_identity_sha256=expected_author,
        independent_scientific_reviewer_identity_sha256=(expected_scientific_reviewer),
        authorization_operator_identity_sha256=expected_operator,
        independent_result_reviewer_identity_sha256=result_reviewer,
        result_reviewer_key_id=key_id,
        reviewed_at_utc=payload["reviewed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        nonce_sha256=payload.get("nonce_sha256"),
        accepted_check_ids=_REQUIRED_RESULT_REVIEW_CHECK_IDS,
        acknowledged_limitation_ids=_REQUIRED_LIMITATION_IDS,
    )
    if payload != expected_projection:
        raise ReferenceValidationResultReviewError(
            "result-review fields or derived dispositions do not match the frozen schema"
        )
    outcome = expected_projection["result_receipt_review_outcome"]
    return ReferenceValidationResultReviewVerification(
        contract_sha256=expected_projection["contract_sha256"],
        result_receipt_sha256=expected_receipt,
        source_manifest_sha256=binding["source_manifest_sha256"],
        attestation_sha256=attestation_sha256,
        implementation_author_identity_sha256=expected_author,
        independent_scientific_reviewer_identity_sha256=(expected_scientific_reviewer),
        authorization_operator_identity_sha256=expected_operator,
        independent_result_reviewer_identity_sha256=result_reviewer,
        result_reviewer_key_id=key_id,
        reviewed_at_utc=payload["reviewed_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        independent_result_review_verified=True,
        implementation_author_separation_verified=True,
        result_receipt_review_outcome=outcome,
        result_receipt_accepted=outcome == RESULT_REVIEW_OUTCOME_ACCEPTED,
        production_validation_evidence=False,
        force_or_energy_validated=False,
        scientifically_validated=False,
        parameter_fitting_proposal_authorized=False,
        parameter_fitting_authorized=False,
        benchmark_validated=False,
        product_qualified=False,
        claim_safe=False,
        blockers=(
            _POST_ATTESTATION_BLOCKERS
            if outcome == RESULT_REVIEW_OUTCOME_ACCEPTED
            else _REJECTED_RESULT_BLOCKERS
        ),
    )


def reference_validation_result_review_contract_decision() -> dict[str, Any]:
    contract = reference_validation_result_review_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "result_review_contract_implemented": True,
        "production_result_receipt_present": False,
        "signed_independent_result_review_present": False,
        "force_or_energy_validated": False,
        "scientifically_validated": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "claim_safe": False,
        "blockers": list(_CLOSED_GATE_BLOCKERS),
    }


__all__ = [
    "CASE_DISPOSITION_ACCEPTED",
    "CASE_DISPOSITION_REJECTED",
    "FAILURE_DISPOSITION_ACCEPTED",
    "FAILURE_DISPOSITION_REJECTED",
    "FROZEN_REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256",
    "METRIC_DISPOSITION_ACCEPTED",
    "METRIC_DISPOSITION_REJECTED",
    "REFERENCE_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID",
    "REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_ID",
    "REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_RESULT_REVIEW_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_RESULT_REVIEW_MAX_VALIDITY",
    "REFERENCE_VALIDATION_RESULT_REVIEW_SIGNATURE_ALGORITHM",
    "RESULT_REVIEW_OUTCOME_ACCEPTED",
    "RESULT_REVIEW_OUTCOME_REJECTED",
    "ResultReviewerTrustAnchor",
    "ReferenceValidationResultReviewError",
    "ReferenceValidationResultReviewVerification",
    "ReferenceValidationResultReviewerTrustAnchor",
    "VARIANT_DISPOSITION_ACCEPTED",
    "VARIANT_DISPOSITION_REJECTED",
    "WORKER_EXECUTION_DISPOSITION_ACCEPTED",
    "WORKER_EXECUTION_DISPOSITION_REJECTED",
    "build_signed_reference_validation_result_review_attestation",
    "reference_validation_result_review_contract_decision",
    "reference_validation_result_review_contract_document",
    "require_reference_validation_result_review_contract_document",
    "verify_signed_reference_validation_result_review_attestation",
]
