from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics import (
    CPU_REFERENCE_VALIDATION_PROTOCOL_SCHEMA_ID,
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
    FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256,
    CPUReferenceValidationProtocolError,
    CPUReferenceValidationSpec,
    cpu_reference_validation_authorization_decision,
    cpu_reference_validation_protocol_document,
    cpu_reference_validation_protocol_json_bytes,
    frozen_cpu_reference_validation_protocol,
    require_cpu_reference_validation_execution_authorized,
    require_cpu_reference_validation_protocol_document,
    write_cpu_reference_validation_protocol_json,
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


def test_frozen_protocol_binds_h5_dependency_cases_thresholds_and_digest() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    document = cpu_reference_validation_protocol_document(protocol)

    assert document["schema_id"] == CPU_REFERENCE_VALIDATION_PROTOCOL_SCHEMA_ID
    assert document["protocol_sha256"] == (
        FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256
    )
    assert FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256 == (
        "1ee318ca1550953022783afa8b88eb66e3698489708c0a96969b855ca2995298"
    )
    assert protocol.protocol_sha256 == document["protocol_sha256"]
    dependencies = document["dependencies"]
    assert dependencies["h5_applicability_record_sha256"] == (
        FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256
    )
    assert dependencies["exact_h5_document_required_at_execution"] is True
    assert (
        dependencies["exact_h5_runtime_source_verification_required_at_execution"]
        is True
    )
    assert dependencies["dependency_claim_status_inherited"] is False


def test_fixture_manifest_is_exact_failure_inclusive_and_result_free() -> None:
    manifest = cpu_reference_validation_protocol_document()["fixture_manifest"]

    assert manifest["status"] == ("specification_only_materializer_not_implemented")
    assert manifest["fixture_count"] == 7
    assert manifest["mutation_count"] == 20
    assert manifest["case_count"] == 27
    assert manifest["expected_pass_case_count"] == 15
    assert manifest["expected_fail_closed_case_count"] == 12
    assert manifest["denominator"] == "all_frozen_cases"
    assert manifest["failure_rows_retained"] is True
    assert manifest["skipped_cases_allowed"] is False

    case_ids = [row["case_id"] for row in manifest["cases"]]
    assert len(case_ids) == len(set(case_ids)) == 27
    assert {
        "bond_energy_force",
        "angle_energy_force",
        "proper_torsion_energy_force",
        "lennard_jones_energy_force",
        "screened_coulomb_energy_force",
        "full_force_central_difference",
        "rigid_translation_invariance",
        "rigid_rotation_invariance",
        "atom_permutation_equivariance",
        "same_environment_repeat_determinism",
        "topology_identity_crosswire",
        "stale_neighbor_graph",
        "minimum_pair_distance_violation",
        "zero_length_angle_vector",
        "collinear_torsion",
    }.issubset(case_ids)
    assert all(len(row["input_sha256"]) == 64 for row in manifest["cases"])
    assert all(len(row["spec_sha256"]) == 64 for row in manifest["fixtures"])
    assert all(len(row["spec_sha256"]) == 64 for row in manifest["mutations"])
    assert not any(
        row["expected_outcome"] == "fail_closed" and not row["expected_error_code"]
        for row in manifest["cases"]
    )
    assert manifest["fixture_manifest_sha256"] == (
        frozen_cpu_reference_validation_protocol().fixture_manifest_sha256
    )


def test_numerical_thresholds_are_predefined_per_value_without_averaging() -> None:
    numerical = cpu_reference_validation_protocol_document()["numerical_protocol"]
    metrics = {row["metric_id"]: row for row in numerical["metrics"]}

    assert numerical["coordinate_dtype"] == "float64"
    assert numerical["energy_unit"] == "kcal/mol"
    assert numerical["force_unit"] == "kcal/mol/angstrom"
    assert numerical["finite_difference"] == {
        "method": "two_sided_central_difference",
        "coordinate_step_angstrom": 1.0e-5,
        "comparison_scope": "every_nonsingular_batch_atom_cartesian_component",
    }
    assert numerical["cross_case_averaging_allowed"] is False
    assert numerical["missing_metric_is_failure"] is True
    assert len(metrics) == 19
    assert metrics["energy_oracle_max_abs_error"]["threshold_value"] == 1.0e-10
    assert metrics["force_oracle_max_component_abs_error"]["threshold_value"] == 1.0e-8
    assert metrics["finite_difference_force_max_abs_error"]["threshold_value"] == 2.0e-4
    assert metrics["minimum_image_energy_abs_error"]["threshold_value"] == 1.0e-12
    assert metrics["repeat_force_bitwise_equal"]["threshold_operator"] == "equal"
    assert all(row["threshold_predefined_before_results"] for row in metrics.values())


def test_protocol_separates_contract_math_from_scientific_force_field_evidence() -> (
    None
):
    document = cpu_reference_validation_protocol_document()
    lanes = document["validation_lanes"]

    synthetic = lanes["synthetic_implementation_mathematics"]
    assert synthetic["status"] == "protocol_frozen_not_executed"
    assert synthetic["parameter_origin"] == ("synthetic_protocol_values_not_fit_data")
    assert synthetic["can_establish_physical_parameter_accuracy"] is False
    assert synthetic["can_establish_chemical_applicability"] is False

    scientific = lanes["scientific_parameterized_force_field"]
    assert scientific["status"] == "not_ready_for_protocol_execution"
    for key in (
        "case_manifest_frozen",
        "reviewed_runtime_parameter_values_bound",
        "chemical_applicability_domain_frozen",
        "independent_holdout_frozen",
        "independent_reference_artifacts_bound",
        "result_collection_allowed",
    ):
        assert scientific[key] is False

    oracle = document["independent_oracle_policy"]
    assert oracle["required_before_execution"] is True
    assert oracle["implemented"] is False
    assert oracle["source_sha256"] is None
    assert (
        "betelgeuze_engine_v2.physics.reference_forcefield"
        in (oracle["must_not_import"])
    )
    assert document["result_receipt"]["created"] is False
    assert document["result_receipt"]["partial_result_promotion_allowed"] is False


def test_authorization_gate_is_executable_exact_and_fail_closed() -> None:
    document = cpu_reference_validation_protocol_document()
    decision = cpu_reference_validation_authorization_decision(document)

    assert decision.protocol_sha256 == document["protocol_sha256"]
    assert decision.validation_execution_authorized is False
    assert decision.parameter_fitting_proposal_authorized is False
    assert "fixture_materializer_not_implemented" in decision.blockers
    assert "independent_analytic_oracle_not_implemented" in decision.blockers
    assert "signed_execution_authorization_receipt_missing" in decision.blockers
    assert "parameter_fitting_not_authorized" in decision.blockers
    assert (
        decision.to_dict()["blockers"]
        == document["authorization_gate"]["current_blockers"]
    )

    with pytest.raises(
        CPUReferenceValidationProtocolError,
        match="execution is not authorized",
    ):
        require_cpu_reference_validation_execution_authorized(document)


def test_all_scientific_benchmark_product_and_customer_claims_remain_false() -> None:
    document = cpu_reference_validation_protocol_document()
    claims = document["claim_policy"]

    assert claims["protocol_definition_frozen"] is True
    assert claims["synthetic_case_identities_frozen"] is True
    assert claims["acceptance_thresholds_predefined"] is True
    assert claims["failure_rows_retained"] is True
    for key in (
        "fixture_materializer_implemented",
        "independent_oracle_implemented",
        "independent_scientific_review_completed",
        "validation_execution_authorized",
        "validation_results_collected",
        "force_or_energy_validated",
        "runtime_parameter_values_independently_reviewed",
        "scientific_applicability_established",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "minimization_validated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert claims[key] is False
    assert document["review"]["independent_scientific_review_completed"] is False
    assert document["review"]["superseded"] is False
    assert document["review"]["revoked"] is False


def test_exact_document_verifier_rejects_digest_and_policy_drift() -> None:
    document = cpu_reference_validation_protocol_document()
    assert require_cpu_reference_validation_protocol_document(document) == document

    tampered = deepcopy(document)
    tampered["authorization_gate"]["validation_execution_authorized"] = True
    with pytest.raises(
        CPUReferenceValidationProtocolError,
        match="digest mismatch",
    ):
        require_cpu_reference_validation_protocol_document(tampered)

    rehashed = deepcopy(tampered)
    projection = {
        key: value for key, value in rehashed.items() if key != "protocol_sha256"
    }
    rehashed["protocol_sha256"] = _canonical_sha256(projection)
    with pytest.raises(
        CPUReferenceValidationProtocolError,
        match="does not match the frozen protocol",
    ):
        require_cpu_reference_validation_protocol_document(rehashed)


def test_protocol_and_spec_validation_reject_review_or_canonical_drift() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    with pytest.raises(CPUReferenceValidationProtocolError, match="superseded"):
        replace(protocol, superseded=True)
    with pytest.raises(CPUReferenceValidationProtocolError, match="canonical JSON"):
        CPUReferenceValidationSpec(
            spec_id="drift",
            kind="fixture_profile",
            canonical_payload_json='{ "value": 1 }',
        )


def test_private_atomic_protocol_writer_round_trips(tmp_path: Path) -> None:
    output = tmp_path / "protocols" / "cpu-reference-validation.json"
    assert write_cpu_reference_validation_protocol_json(output) == (
        FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256
    )
    assert output.read_bytes() == cpu_reference_validation_protocol_json_bytes()
    assert (
        require_cpu_reference_validation_protocol_document(
            json.loads(output.read_text(encoding="ascii"))
        )
        == cpu_reference_validation_protocol_document()
    )
    assert os.stat(output).st_mode & 0o777 == 0o600

    symlink = tmp_path / "protocol-link.json"
    symlink.symlink_to(output)
    with pytest.raises(CPUReferenceValidationProtocolError, match="symlink"):
        write_cpu_reference_validation_protocol_json(symlink)


def test_protocol_is_integrated_into_canonical_docs_and_ci() -> None:
    status = Path("docs/engine_v2_status.md").read_text(encoding="utf-8")
    public_api = Path("docs/engine_v2_public_api.md").read_text(encoding="utf-8")
    roadmap = Path("docs/independent_engine_v2_commercial_roadmap.ko.md").read_text(
        encoding="utf-8"
    )
    scientific = Path(
        "docs/roadmaps/engine-v2-scientific-evidence-roadmap.md"
    ).read_text(encoding="utf-8")
    focused_workflow = Path(
        ".github/workflows/ci-engine-v2-cpu-reference-validation-protocol.yml"
    ).read_text(encoding="utf-8")
    main_workflow = Path(".github/workflows/ci-engine-v2-main.yml").read_text(
        encoding="utf-8"
    )

    assert "v2_m_cpu_reference_validation_artifacts" in status
    assert "reference_validation_protocol" in public_api
    assert "reference_validation_artifact_binding" in public_api
    assert "v2_cpu_reference_energy_force_validation_protocol" in roadmap
    assert "twenty-seven ordered pass/fail-closed cases" in scientific
    for source in (focused_workflow, main_workflow):
        assert "test_engine_v2_cpu_reference_validation_protocol.py" in source
        assert "test_engine_v2_reference_validation_artifacts.py" in source
        assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "reference_validation_artifact_authorization_decision" in main_workflow
