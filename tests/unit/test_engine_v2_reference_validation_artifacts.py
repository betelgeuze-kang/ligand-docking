from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import canonical_topology_sha256  # noqa: E402
from betelgeuze_engine_v2.physics import (  # noqa: E402
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
    FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256,
    FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
    FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256,
    IndependentAnalyticOracleInput,
    IndependentAnalyticOracleError,
    ReferenceValidationArtifactBindingError,
    evaluate_independent_analytic_oracle,
    frozen_cpu_reference_validation_protocol,
    independent_analytic_oracle_source_sha256,
    materialize_frozen_reference_validation_case,
    reference_validation_artifact_authorization_decision,
    reference_validation_artifact_binding_document,
    reference_validation_artifact_binding_json_bytes,
    reference_validation_materialization_manifest_document,
    reference_validation_materializer_source_sha256,
    require_reference_validation_artifact_binding_document,
    require_reference_validation_execution_authorized,
    write_reference_validation_artifact_binding_json,
)


def _bond_input(distance: float) -> IndependentAnalyticOracleInput:
    return IndependentAnalyticOracleInput(
        coordinates_angstrom=((0.0, 0.0, 0.0), (distance, 0.0, 0.0)),
        topology_bonds=((0, 1),),
        atom_nonbonded=((0, 3.0, 0.0, 0.0), (1, 3.0, 0.0, 0.0)),
        bonds=((0, 1, 1.0, 100.0),),
        excluded_pairs=((0, 1),),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
    )


def _lj_input(distance: float) -> IndependentAnalyticOracleInput:
    return IndependentAnalyticOracleInput(
        coordinates_angstrom=((0.0, 0.0, 0.0), (distance, 0.0, 0.0)),
        topology_bonds=(),
        atom_nonbonded=((0, 3.0, 0.2, 0.0), (1, 3.0, 0.2, 0.0)),
        cutoff_angstrom=6.0,
        switch_start_angstrom=5.0,
    )


def test_artifact_binding_freezes_exact_sources_and_dependencies() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    document = reference_validation_artifact_binding_document()

    assert protocol.protocol_sha256 == FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256
    assert document["binding_sha256"] == (FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256)
    assert document["dependencies"] == {
        "protocol_sha256": protocol.protocol_sha256,
        "fixture_manifest_sha256": protocol.fixture_manifest_sha256,
        "h5_applicability_record_sha256": (protocol.h5_applicability_record_sha256),
        "exact_dependencies_required": True,
        "dependency_claim_status_inherited": False,
    }
    assert document["materializer"]["source_sha256"] == (FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256)
    assert document["independent_oracle"]["source_sha256"] == (FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256)
    assert reference_validation_materializer_source_sha256() == (FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256)
    assert independent_analytic_oracle_source_sha256() == (FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256)

    audit = document["independent_oracle"]["import_audit"]
    assert audit["audit_passed"] is True
    assert audit["imports"] == [
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "math",
        "numbers",
        "typing",
    ]
    assert audit["reference_evaluator_imported"] is False
    assert audit["validation_protocol_imported"] is False
    assert audit["third_party_dependency_imported"] is False
    assert document["independent_oracle"]["external_molecular_solver_used"] is False
    assert document["independent_oracle"]["third_party_numeric_runtime_used"] is False


def test_artifact_binding_keeps_every_claim_and_execution_gate_closed() -> None:
    document = reference_validation_artifact_binding_document()
    gate = document["authorization_gate"]
    policy = document["claim_policy"]

    assert gate["status"] == "closed"
    assert gate["validation_execution_authorized"] is False
    assert gate["parameter_fitting_proposal_authorized"] is False
    assert gate["parameter_fitting_authorized"] is False
    assert gate["signed_authorization_receipt_schema_frozen"] is False
    assert gate["signed_authorization_receipt_present"] is False
    assert gate["current_blockers"] == document["blockers"]
    assert len(document["blockers"]) == 13

    assert policy["fixture_materializer_implemented"] is True
    assert policy["independent_oracle_implemented"] is True
    assert policy["independent_oracle_import_boundary_verified"] is True
    for field in (
        "validation_execution_authorized",
        "validation_results_collected",
        "force_or_energy_validated",
        "runtime_parameter_values_independently_reviewed",
        "scientific_applicability_established",
        "independent_scientific_review_completed",
        "parameter_fitting_proposal_authorized",
        "parameter_fitting_authorized",
        "minimization_validated",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert policy[field] is False

    decision = reference_validation_artifact_authorization_decision(document)
    assert decision.validation_execution_authorized is False
    assert decision.parameter_fitting_proposal_authorized is False
    assert decision.parameter_fitting_authorized is False
    assert decision.blockers == tuple(document["blockers"])
    with pytest.raises(
        ReferenceValidationArtifactBindingError,
        match="execution remains unauthorized",
    ):
        require_reference_validation_execution_authorized(document)


def test_materialization_manifest_is_exact_complete_and_result_free() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    first = reference_validation_materialization_manifest_document(protocol)
    second = reference_validation_materialization_manifest_document(protocol)

    assert first == second
    assert first["protocol_sha256"] == protocol.protocol_sha256
    assert first["fixture_manifest_sha256"] == protocol.fixture_manifest_sha256
    assert first["coverage"] == {
        "fixture_count": 7,
        "mutation_count": 20,
        "case_count": 27,
        "variant_count": 59,
        "expected_pass_case_count": 15,
        "expected_fail_closed_case_count": 12,
    }
    assert [row["case_id"] for row in first["cases"]] == [row.case_id for row in protocol.cases]
    assert {row["mutation_contract_id"] for row in first["cases"]} == {row.spec_id for row in protocol.mutations}
    assert first["result_collection_performed"] is False
    assert first["energy_or_force_values_present"] is False
    assert first["metric_values_present"] is False
    assert first["validation_execution_authorized"] is False
    assert first["scientifically_validated"] is False
    assert first["claim_safe"] is False
    for case in first["cases"]:
        assert case["result_fields_present"] is False
        assert len(case["materialization_sha256"]) == 64
        for variant in case["variants"]:
            assert variant["energy_or_force_evaluated"] is False
            assert variant["validation_result_collected"] is False
            assert variant["scientifically_validated"] is False
            assert variant["claim_safe"] is False
            assert variant["coordinate_dtype"] == "float64"
            assert variant["device"] == "cpu"


def test_materializer_expands_every_multi_variant_mutation_exactly() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    expected_counts = {
        "quintic_switch_window_and_cutoff": 3,
        "orthorhombic_minimum_image": 2,
        "full_force_central_difference": 25,
        "rigid_translation_invariance": 2,
        "rigid_rotation_invariance": 2,
        "atom_permutation_equivariance": 2,
        "same_environment_repeat_determinism": 3,
    }
    for case in protocol.cases:
        materialized = materialize_frozen_reference_validation_case(case.case_id, protocol)
        assert len(materialized.variants) == expected_counts.get(case.case_id, 1)
        assert materialized.case_input_sha256 == case.input_sha256
        assert materialized.fixture_profile_sha256 == case.fixture_profile_sha256
        assert materialized.mutation_contract_sha256 == (case.mutation_contract_sha256)
        if case.expected_outcome == "pass":
            assert materialized.expected_error_code is None
            assert all(row.oracle_input is not None for row in materialized.variants)
            assert all(
                row.parameters.topology_sha256 == canonical_topology_sha256(row.system) for row in materialized.variants
            )
        else:
            assert materialized.expected_error_code == case.expected_error_code
            assert all(row.oracle_input is None for row in materialized.variants)


def test_fail_closed_materializations_encode_the_intended_invalidity() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    by_id = {
        row.case_id: materialize_frozen_reference_validation_case(row.case_id, protocol).variants[0]
        for row in protocol.cases
        if row.expected_outcome == "fail_closed"
    }

    crosswire = by_id["topology_identity_crosswire"]
    assert crosswire.parameters.topology_sha256 != canonical_topology_sha256(crosswire.system)
    assert len(by_id["missing_nonbonded_parameter"].parameters.atom_parameters) == 3
    assert len(by_id["missing_bond_parameter"].parameters.bonds) == 2
    assert len(by_id["missing_angle_parameter"].parameters.angles) == 1
    assert len(by_id["missing_torsion_parameter"].parameters.torsions) == 0
    assert by_id["neighbor_cutoff_too_short"].neighbors.diagnostics.cutoff_angstrom == 4.0
    assert by_id["atom_capacity_overflow"].parameters.applicability_domain.max_atoms == 3
    minimum_pair = by_id["minimum_pair_distance_violation"].system.coordinates[0]
    assert math.isclose(
        float(torch.linalg.vector_norm(minimum_pair[0] - minimum_pair[1]).item()),
        1.0e-8,
        rel_tol=0.0,
        abs_tol=1.0e-20,
    )
    assert by_id["periodic_half_box_cutoff"].parameters.cutoff_angstrom == 5.0
    zero_angle = by_id["zero_length_angle_vector"].system.coordinates[0]
    assert torch.equal(zero_angle[0], zero_angle[1])
    collinear = by_id["collinear_torsion"].system.coordinates[0]
    assert torch.equal(collinear[:, 1:], torch.zeros_like(collinear[:, 1:]))


def test_independent_oracle_matches_hand_derived_harmonic_bond_solution() -> None:
    evaluation = evaluate_independent_analytic_oracle(_bond_input(1.2))
    components = dict(evaluation.component_energies_kcal_per_mol)

    assert evaluation.total_energy_kcal_per_mol == pytest.approx(2.0, abs=1.0e-14)
    assert components["harmonic_bond"] == pytest.approx(2.0, abs=1.0e-14)
    for name in (
        "harmonic_angle",
        "periodic_torsion",
        "lennard_jones",
        "screened_coulomb",
    ):
        assert components[name] == 0.0
    assert tuple(value for row in evaluation.forces_kcal_per_mol_angstrom for value in row) == pytest.approx(
        (20.0, 0.0, 0.0, -20.0, 0.0, 0.0), abs=1.0e-12
    )

    equilibrium = evaluate_independent_analytic_oracle(_bond_input(1.0))
    assert equilibrium.total_energy_kcal_per_mol == 0.0
    assert equilibrium.forces_kcal_per_mol_angstrom == (
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )


def test_independent_oracle_matches_hand_derived_lj_sigma_solution() -> None:
    evaluation = evaluate_independent_analytic_oracle(_lj_input(3.0))
    components = dict(evaluation.component_energies_kcal_per_mol)

    assert evaluation.total_energy_kcal_per_mol == pytest.approx(0.0, abs=1.0e-14)
    assert components["lennard_jones"] == pytest.approx(0.0, abs=1.0e-14)
    assert tuple(value for row in evaluation.forces_kcal_per_mol_angstrom for value in row) == pytest.approx(
        (-1.6, 0.0, 0.0, 1.6, 0.0, 0.0), abs=1.0e-12
    )


def test_independent_oracle_self_consistency_for_invariance_variants() -> None:
    protocol = frozen_cpu_reference_validation_protocol()
    translation = materialize_frozen_reference_validation_case("rigid_translation_invariance", protocol)
    rotation = materialize_frozen_reference_validation_case("rigid_rotation_invariance", protocol)
    permutation = materialize_frozen_reference_validation_case("atom_permutation_equivariance", protocol)

    translated = [evaluate_independent_analytic_oracle(row.oracle_input) for row in translation.variants]
    rotated = [evaluate_independent_analytic_oracle(row.oracle_input) for row in rotation.variants]
    permuted = [evaluate_independent_analytic_oracle(row.oracle_input) for row in permutation.variants]
    assert translated[0].total_energy_kcal_per_mol == pytest.approx(
        translated[1].total_energy_kcal_per_mol, abs=1.0e-12
    )
    assert rotated[0].total_energy_kcal_per_mol == pytest.approx(rotated[1].total_energy_kcal_per_mol, abs=1.0e-12)
    assert permuted[0].total_energy_kcal_per_mol == pytest.approx(permuted[1].total_energy_kcal_per_mol, abs=1.0e-12)
    for evaluation in (*translated, *rotated, *permuted):
        assert math.isfinite(evaluation.total_energy_kcal_per_mol)
        assert all(math.isfinite(value) for row in evaluation.forces_kcal_per_mol_angstrom for value in row)
        assert evaluation.to_dict()["validation_receipt"] is False
        assert evaluation.to_dict()["scientifically_validated"] is False
        assert evaluation.to_dict()["claim_safe"] is False


def test_independent_oracle_uses_stable_singularity_error_codes() -> None:
    zero_angle = IndependentAnalyticOracleInput(
        coordinates_angstrom=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        topology_bonds=((0, 1), (1, 2)),
        atom_nonbonded=(
            (0, 1.0, 0.0, 0.0),
            (1, 1.0, 0.0, 0.0),
            (2, 1.0, 0.0, 0.0),
        ),
        angles=((0, 1, 2, 1.0, 1.0),),
        excluded_pairs=((0, 1), (0, 2), (1, 2)),
        cutoff_angstrom=4.0,
        switch_start_angstrom=3.0,
    )
    with pytest.raises(IndependentAnalyticOracleError, match="angle_zero_length_vector"):
        evaluate_independent_analytic_oracle(zero_angle)

    collinear_torsion = IndependentAnalyticOracleInput(
        coordinates_angstrom=(
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
        ),
        topology_bonds=((0, 1), (1, 2), (2, 3)),
        atom_nonbonded=tuple((index, 1.0, 0.0, 0.0) for index in range(4)),
        torsions=((0, 1, 2, 3, 3, 0.0, 0.5),),
        excluded_pairs=tuple((first, second) for first in range(4) for second in range(first + 1, 4)),
        cutoff_angstrom=6.0,
        switch_start_angstrom=5.0,
    )
    with pytest.raises(
        IndependentAnalyticOracleError,
        match="torsion_undefined_for_collinear_atoms",
    ):
        evaluate_independent_analytic_oracle(collinear_torsion)


def test_binding_verifier_rejects_any_tamper() -> None:
    document = reference_validation_artifact_binding_document()
    assert require_reference_validation_artifact_binding_document(document) == document

    tampered = deepcopy(document)
    tampered["materializer"]["all_frozen_mutations_materialized"] = False
    with pytest.raises(
        ReferenceValidationArtifactBindingError,
        match="does not match the frozen record",
    ):
        require_reference_validation_artifact_binding_document(tampered)

    tampered = deepcopy(document)
    tampered["authorization_gate"]["validation_execution_authorized"] = True
    with pytest.raises(ReferenceValidationArtifactBindingError):
        require_reference_validation_artifact_binding_document(tampered)


def test_binding_serialization_and_private_atomic_writer(tmp_path: Path) -> None:
    document = reference_validation_artifact_binding_document()
    encoded = reference_validation_artifact_binding_json_bytes()
    assert json.loads(encoded) == document
    assert encoded.endswith(b"\n")

    destination = tmp_path / "binding.json"
    digest = write_reference_validation_artifact_binding_json(destination)
    assert digest == FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256
    assert json.loads(destination.read_text(encoding="ascii")) == document
    assert oct(os.stat(destination).st_mode & 0o777) == "0o600"

    target = tmp_path / "target.json"
    target.write_text("preserve", encoding="ascii")
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(target)
    with pytest.raises(
        ReferenceValidationArtifactBindingError,
        match="symlink",
    ):
        write_reference_validation_artifact_binding_json(symlink)
    assert target.read_text(encoding="ascii") == "preserve"
