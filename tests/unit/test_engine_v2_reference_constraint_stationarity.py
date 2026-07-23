from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
import torch

from betelgeuze_engine_v2.physics.reference_constraint_stationarity import (
    REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256,
    ReferenceConstraintStationarityConfig,
    ReferenceConstraintStationarityError,
    minimize_reference_constraint_stationarity,
    reference_constraint_stationarity_default_configuration_document,
    require_reference_constraint_stationarity_checkpoint_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    materialize_frozen_cpu_minimization_validation_case,
)


NONCHARGED_CASE = "v2_constrained_angle_energy_decrease"
FIXED_BORN_CASE = "v2_fixed_born_constrained_energy_decrease"


@pytest.fixture(scope="module")
def candidate_results():
    results = {}
    for case_id in (NONCHARGED_CASE, FIXED_BORN_CASE):
        case = materialize_frozen_cpu_minimization_validation_case(case_id)
        results[case_id] = minimize_reference_constraint_stationarity(
            case.system,
            case.v2_parameters,
            solvation_parameters=case.solvation_parameters,
        )
    return results


def test_default_candidate_configuration_is_preregistered_and_claim_closed() -> None:
    document = reference_constraint_stationarity_default_configuration_document()
    config = document["configuration"]

    assert (
        document["configuration_sha256"]
        == REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
        == "5642654a25a2d024f7cb8c1de024815f6bf6032b06f6c57509d7b784b708f708"
    )
    assert config["strict_projection_tolerance_angstrom"] == 1.0e-14
    assert config["constraint_acceptance_tolerance_angstrom"] == 1.0e-10
    assert config["tangent_force_tolerance_kcal_per_mol_angstrom"] == 1.0e-8
    assert config["stationarity_energy_relaxation_kcal_per_mol"] == 1.0e-10
    assert document["native_openmm_lbfgs_claim"] == "unchanged_rejected_6_of_8"
    assert document["frozen_receipts_modified"] is False
    assert document["validation_receipt"] is False
    assert document["scientifically_validated"] is False
    assert document["claim_safe"] is False
    assert "two_cpu_host_reproduction_missing" in document["scientific_blockers"]


def test_candidate_config_rejects_inconsistent_internal_tolerances() -> None:
    with pytest.raises(
        ReferenceConstraintStationarityError,
        match="strict projection tolerance",
    ):
        ReferenceConstraintStationarityConfig(
            strict_projection_tolerance_angstrom=1.0e-9,
        )
    with pytest.raises(
        ReferenceConstraintStationarityError,
        match="tangent projection tolerance",
    ):
        ReferenceConstraintStationarityConfig(
            tangent_projection_tolerance_kcal_per_mol_angstrom=1.0e-7,
        )


@pytest.mark.parametrize(
    ("case_id", "expected_armijo", "expected_polish"),
    (
        (NONCHARGED_CASE, 181, 0),
        (FIXED_BORN_CASE, 114, 8),
    ),
)
def test_candidate_reaches_constraint_and_absolute_stationarity_together(
    candidate_results,
    case_id: str,
    expected_armijo: int,
    expected_polish: int,
) -> None:
    result = candidate_results[case_id]
    document = result.to_dict()

    assert result.status == "converged"
    assert result.failure_code is None
    assert result.final_max_tangent_force_kcal_per_mol_angstrom <= 1.0e-8
    assert result.final_max_constraint_residual_angstrom <= 1.0e-14
    assert result.accepted_armijo_iterations == expected_armijo
    assert result.accepted_stationarity_polish_iterations == expected_polish
    assert result.accepted_iterations == expected_armijo + expected_polish
    assert result.rejected_trials == 0
    assert result.energy_evaluation_count == result.accepted_iterations + 1
    assert len(result.observations) == result.accepted_iterations + 1
    assert len(document["coordinate_trace"]) == len(result.observations)
    assert len(document["energy_trace_kcal_per_mol"]) == len(result.observations)
    assert document["scientifically_validated"] is False
    assert document["claim_safe"] is False
    assert document["result_sha256"] == result.result_sha256


def test_acceptance_trace_enforces_descent_or_bounded_stationarity_polish(
    candidate_results,
) -> None:
    result = candidate_results[FIXED_BORN_CASE]
    config = ReferenceConstraintStationarityConfig()
    current_energy = result.initial_energy_kcal_per_mol
    current_tangent = (
        result.initial_max_tangent_force_kcal_per_mol_angstrom
    )
    best_energy = current_energy

    for row in result.observations[1:]:
        assert row.energy_kcal_per_mol is not None
        assert row.max_tangent_force_kcal_per_mol_angstrom is not None
        if row.outcome == "accepted_armijo":
            assert row.directional_derivative_kcal_per_mol is not None
            assert row.directional_derivative_kcal_per_mol < 0.0
            assert row.armijo_limit_kcal_per_mol is not None
            assert row.energy_kcal_per_mol <= row.armijo_limit_kcal_per_mol
        else:
            assert row.outcome == "accepted_stationarity_polish"
            assert row.max_tangent_force_kcal_per_mol_angstrom < current_tangent
            assert row.energy_kcal_per_mol <= (
                best_energy
                + config.stationarity_energy_relaxation_kcal_per_mol
            )
        current_energy = row.energy_kcal_per_mol
        current_tangent = row.max_tangent_force_kcal_per_mol_angstrom
        best_energy = min(best_energy, current_energy)
        assert row.max_constraint_residual_angstrom <= (
            config.strict_projection_tolerance_angstrom
        )
    assert current_energy == result.final_energy_kcal_per_mol
    assert best_energy == result.best_energy_kcal_per_mol
    assert (
        result.final_energy_kcal_per_mol - result.best_energy_kcal_per_mol
        <= config.stationarity_energy_relaxation_kcal_per_mol
    )


@pytest.mark.parametrize(
    ("base_case_id", "checkpoint_case_id"),
    (
        (
            NONCHARGED_CASE,
            "v2_constrained_checkpoint_restart_exact",
        ),
        (
            FIXED_BORN_CASE,
            "v2_fixed_born_checkpoint_restart_exact",
        ),
    ),
)
def test_candidate_checkpoint_restart_is_document_exact(
    candidate_results,
    base_case_id: str,
    checkpoint_case_id: str,
) -> None:
    case = materialize_frozen_cpu_minimization_validation_case(
        checkpoint_case_id
    )
    paused = minimize_reference_constraint_stationarity(
        case.system,
        case.v2_parameters,
        solvation_parameters=case.solvation_parameters,
        pause_after_accepted_iterations=3,
    )
    assert paused.status == "checkpointed"
    checkpoint = require_reference_constraint_stationarity_checkpoint_document(
        paused.checkpoint.to_dict()
    )
    resumed = minimize_reference_constraint_stationarity(
        case.system,
        case.v2_parameters,
        solvation_parameters=case.solvation_parameters,
        checkpoint=checkpoint,
    )

    assert resumed.to_dict() == candidate_results[base_case_id].to_dict()


def test_checkpoint_tamper_and_crosswire_are_rejected() -> None:
    case = materialize_frozen_cpu_minimization_validation_case(FIXED_BORN_CASE)
    paused = minimize_reference_constraint_stationarity(
        case.system,
        case.v2_parameters,
        solvation_parameters=case.solvation_parameters,
        pause_after_accepted_iterations=3,
    )
    tampered = deepcopy(paused.checkpoint.to_dict())
    tampered["current_energy_kcal_per_mol"] += 1.0
    with pytest.raises(
        ReferenceConstraintStationarityError,
        match="current state|document digest",
    ):
        require_reference_constraint_stationarity_checkpoint_document(tampered)

    without_solvation = materialize_frozen_cpu_minimization_validation_case(
        NONCHARGED_CASE
    )
    with pytest.raises(
        ReferenceConstraintStationarityError,
        match="source system identity|parameter identity|solvation parameter identity",
    ):
        minimize_reference_constraint_stationarity(
            without_solvation.system,
            without_solvation.v2_parameters,
            checkpoint=paused.checkpoint,
        )


def test_iteration_budget_failure_retains_terminal_state_and_all_rows() -> None:
    case = materialize_frozen_cpu_minimization_validation_case(FIXED_BORN_CASE)
    result = minimize_reference_constraint_stationarity(
        case.system,
        case.v2_parameters,
        ReferenceConstraintStationarityConfig(max_iterations=1),
        solvation_parameters=case.solvation_parameters,
    )

    assert result.status == "max_iterations_reached"
    assert result.failure_code == "maximum_iteration_budget_exhausted"
    assert result.accepted_iterations == 1
    assert result.rejected_trials == 0
    assert tuple(row.attempt_index for row in result.observations) == (0, 1)
    assert result.checkpoint.observations == result.observations
    assert (
        require_reference_constraint_stationarity_checkpoint_document(
            result.checkpoint.to_dict()
        ).to_dict()
        == result.checkpoint.to_dict()
    )


def test_line_search_failure_retains_every_rejected_trial() -> None:
    case = materialize_frozen_cpu_minimization_validation_case(FIXED_BORN_CASE)
    result = minimize_reference_constraint_stationarity(
        case.system,
        case.v2_parameters,
        ReferenceConstraintStationarityConfig(
            max_iterations=20,
            max_backtracks=0,
            initial_step_size_angstrom2_mol_per_kcal=0.1,
        ),
        solvation_parameters=case.solvation_parameters,
    )

    assert result.status == "line_search_failed"
    assert result.failure_code == "bounded_stationarity_backtracking_exhausted"
    assert result.accepted_iterations == 1
    assert result.rejected_trials == 1
    failure_rows = [
        row for row in result.observations if row.failure_code is not None
    ]
    assert len(failure_rows) == result.rejected_trials
    assert failure_rows[0].outcome == "rejected_displacement"
    assert failure_rows[0].failure_code == "projected_displacement_bound_exceeded"
    assert tuple(row.attempt_index for row in result.observations) == (0, 1, 2)


def test_candidate_rejects_non_cpu_float64_coordinates() -> None:
    case = materialize_frozen_cpu_minimization_validation_case(NONCHARGED_CASE)
    invalid = replace(
        case.system,
        coordinates=case.system.coordinates.to(dtype=torch.float32),
    )
    with pytest.raises(
        ReferenceConstraintStationarityError,
        match="CPU float64",
    ):
        minimize_reference_constraint_stationarity(
            invalid,
            case.v2_parameters,
        )
