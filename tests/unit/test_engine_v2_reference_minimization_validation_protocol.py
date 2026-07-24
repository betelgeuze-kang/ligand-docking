from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_REFREEZE_REASON,
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_SCHEMA_ID,
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    SUPERSEDED_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    CPUMinimizationValidationProtocolError,
    cpu_minimization_validation_authorization_decision,
    cpu_minimization_validation_case_atom_count,
    cpu_minimization_validation_protocol_document,
    cpu_minimization_validation_protocol_json_bytes,
    require_cpu_minimization_validation_execution_authorized,
    require_cpu_minimization_validation_protocol_document,
    write_cpu_minimization_validation_protocol_json,
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def test_protocol_freezes_exact_source_case_and_metric_identities() -> None:
    document = cpu_minimization_validation_protocol_document()

    assert document["schema_id"] == CPU_MINIMIZATION_VALIDATION_PROTOCOL_SCHEMA_ID
    assert document["protocol_sha256"] == (
        FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
    )
    assert FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256 == (
        "380de5fcdc22ccc6cdbc86977652ca0695919f714859d1c4935b1ea3e0a5da5b"
    )
    assert SUPERSEDED_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256 == (
        "41be727dca217152ec57c7194f128196f4cd7e88c7297ffe68bccaf64274d7cb"
    )
    assert document["superseded_protocol_sha256"] == (
        SUPERSEDED_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
    )
    assert document["refreeze_reason"] == (
        CPU_MINIMIZATION_VALIDATION_PROTOCOL_REFREEZE_REASON
    )
    assert document["dependencies"]["exact_source_identity_required_at_execution"]
    source_hashes = document["dependencies"]["source_sha256"]
    assert set(source_hashes) == {
        "reference_constrained_minimization.py",
        "reference_forcefield.py",
        "reference_forcefield_v2.py",
        "reference_minimization.py",
        "reference_solvation.py",
    }
    assert all(len(value) == 64 for value in source_hashes.values())
    assert document["dependencies"]["source_set_sha256"] == _canonical_sha256(
        source_hashes
    )
    assert tuple(
        cpu_minimization_validation_case_atom_count(row["case_id"])
        for row in document["case_manifest"]["cases"]
    ) == (2, 4, 4, 2, 3, 3, 3, 3, 4, 4, 3, 3, 4, 3)


def test_fixture_manifest_freezes_exact_payloads_and_binds_every_case() -> None:
    document = cpu_minimization_validation_protocol_document()
    manifest = document["fixture_manifest"]
    rows = manifest["fixtures"]

    assert manifest["fixture_count"] == 11
    assert manifest["fixture_order"] == "lexicographic_fixture_id"
    assert manifest["materializer_implemented"] is False
    assert len({row["fixture_id"] for row in rows}) == 11
    assert all(len(row["fixture_sha256"]) == 64 for row in rows)
    assert manifest["fixture_manifest_sha256"] == (
        "fe8f41534ed03c37c6a509f9ce3fdddf0b2ed462e0d9c3c3a1a2b6410cb633dc"
    )
    assert manifest["fixture_manifest_sha256"] == _canonical_sha256(rows)

    fixtures = {row["fixture_id"]: row for row in rows}
    charged = fixtures["three_atom_charged_constrained_angle"]["payload"]
    assert [row[0] for row in charged["atom_nonbonded"]] == [0.8, -0.4, -0.4]
    assert charged["fixed_born"]["effective_radii_angstrom"] == [1.5, 1.6, 1.7]
    inconsistent = fixtures["constraint_projection_budget_exhaustion"]["payload"]
    assert inconsistent["distance_constraints"] == [
        [0, 1, 1.0],
        [1, 2, 1.0],
        [0, 2, 3.0],
    ]

    for case in document["case_manifest"]["cases"]:
        fixture_id = case["canonical_input"]["fixture"]
        assert case["canonical_input"]["fixture_sha256"] == fixtures[fixture_id][
            "fixture_sha256"
        ]


def test_case_manifest_is_ordered_failure_inclusive_and_result_free() -> None:
    document = cpu_minimization_validation_protocol_document()
    manifest = document["case_manifest"]

    assert manifest["case_count"] == 14
    assert manifest["expected_pass_case_count"] == 8
    assert manifest["expected_fail_closed_case_count"] == 6
    assert manifest["denominator"] == "all_frozen_cases"
    assert manifest["failure_rows_retained"] is True
    assert manifest["skipped_cases_allowed"] is False
    assert manifest["case_order_is_semantic"] is True
    rows = manifest["cases"]
    assert len({row["case_id"] for row in rows}) == 14
    assert all(len(row["input_sha256"]) == 64 for row in rows)
    assert manifest["case_manifest_sha256"] == _canonical_sha256(rows)
    assert {
        "v1_checkpoint_restart_exact",
        "v2_constrained_checkpoint_restart_exact",
        "v2_fixed_born_checkpoint_restart_exact",
        "checkpoint_topology_crosswire",
        "checkpoint_parameter_crosswire",
        "checkpoint_solvation_crosswire",
        "fixed_born_periodic_cell_rejected",
        "line_search_budget_exhausted",
        "constraint_projection_budget_exhausted",
    }.issubset({row["case_id"] for row in rows})
    assert not any(
        row["expected_outcome"] == "fail_closed"
        and (
            row["required_metric_ids"]
            or not row["expected_error_code"]
        )
        for row in rows
    )
    assert document["result_receipt"]["created"] is False


def test_metrics_predefine_independent_reference_and_constraint_thresholds() -> None:
    numerical = cpu_minimization_validation_protocol_document()[
        "numerical_protocol"
    ]
    metrics = {row["metric_id"]: row for row in numerical["metrics"]}

    assert numerical["coordinate_dtype"] == "float64"
    assert numerical["device"] == "cpu"
    assert numerical["cross_case_averaging_allowed"] is False
    assert numerical["missing_metric_is_failure"] is True
    assert numerical["partial_success_promotion_allowed"] is False
    assert len(metrics) == 10
    assert metrics["constraint_max_abs_residual"]["threshold_value"] == 1.0e-10
    assert metrics["final_tangent_force_max_abs"]["threshold_value"] == 1.0e-7
    assert metrics["checkpoint_resume_bitwise_equal"]["threshold_operator"] == (
        "equal"
    )
    assert metrics[
        "independent_reference_final_coordinate_max_abs_error"
    ]["threshold_value"] == 1.0e-8
    assert metrics[
        "independent_reference_final_energy_abs_error"
    ]["threshold_value"] == 1.0e-10
    assert all(row["threshold_predefined_before_results"] for row in metrics.values())


def test_independent_reference_and_claim_boundaries_remain_closed() -> None:
    document = cpu_minimization_validation_protocol_document()
    independent = document["independent_reference_policy"]

    assert independent["required_before_execution"] is True
    assert independent["implemented"] is False
    assert independent["source_sha256"] is None
    assert independent["artifact_manifest_sha256"] is None
    assert independent[
        "same_evaluator_finite_difference_is_independent_evidence"
    ] is False

    claims = document["claim_policy"]
    for key in (
        "fixture_materializer_implemented",
        "independent_reference_implemented",
        "independent_scientific_review_completed",
        "execution_authorized",
        "validation_results_collected",
        "minimization_validated",
        "solvated_minimization_validated",
        "runtime_parameter_values_independently_reviewed",
        "scientific_applicability_established",
        "parameter_fitting_authorized",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert claims[key] is False


def test_authorization_gate_is_exact_and_always_fail_closed() -> None:
    document = cpu_minimization_validation_protocol_document()
    decision = cpu_minimization_validation_authorization_decision(document)

    assert decision.protocol_sha256 == document["protocol_sha256"]
    assert decision.execution_authorized is False
    assert decision.parameter_fitting_authorized is False
    assert "independent_minimization_reference_not_bound" in decision.blockers
    assert "independent_scientific_review_missing" in decision.blockers
    assert "production_result_receipt_missing" in decision.blockers
    assert "parameter_fitting_not_authorized" in decision.blockers

    with pytest.raises(
        CPUMinimizationValidationProtocolError,
        match="execution is not authorized",
    ):
        require_cpu_minimization_validation_execution_authorized(document)


def test_exact_document_verifier_rejects_digest_and_policy_drift() -> None:
    document = cpu_minimization_validation_protocol_document()
    assert require_cpu_minimization_validation_protocol_document(document) == document

    tampered = deepcopy(document)
    tampered["claim_policy"]["minimization_validated"] = True
    with pytest.raises(
        CPUMinimizationValidationProtocolError,
        match="digest mismatch",
    ):
        require_cpu_minimization_validation_protocol_document(tampered)

    rehashed = deepcopy(tampered)
    projection = {
        key: value for key, value in rehashed.items() if key != "protocol_sha256"
    }
    rehashed["protocol_sha256"] = _canonical_sha256(projection)
    with pytest.raises(
        CPUMinimizationValidationProtocolError,
        match="frozen identity",
    ):
        require_cpu_minimization_validation_protocol_document(rehashed)


def test_canonical_json_and_atomic_writer_round_trip(tmp_path: Path) -> None:
    payload = cpu_minimization_validation_protocol_json_bytes()
    assert payload.endswith(b"\n")
    assert json.loads(payload) == cpu_minimization_validation_protocol_document()
    assert payload == (
        json.dumps(
            json.loads(payload),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )

    destination = write_cpu_minimization_validation_protocol_json(
        tmp_path / "nested" / "protocol.json"
    )
    assert destination.read_bytes() == payload
    assert os.stat(destination).st_mode & 0o777 == 0o644
