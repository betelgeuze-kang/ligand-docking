from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_constrained_minimization import (
    minimize_reference_force_field_v2_constrained,
)
from betelgeuze_engine_v2.physics.reference_minimization import (
    minimize_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_minimization_independent_oracle import (
    IndependentMinimizationOracleError,
    evaluate_independent_minimization_oracle,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    cpu_minimization_validation_materialization_manifest_document,
    materialize_frozen_cpu_minimization_validation_case,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)


PASS_CASE_IDS = (
    "v1_bonded_energy_decrease",
    "v1_mixed_term_energy_decrease",
    "v1_checkpoint_restart_exact",
    "v1_initially_converged_noop",
    "v2_constrained_angle_energy_decrease",
    "v2_constrained_checkpoint_restart_exact",
    "v2_fixed_born_constrained_energy_decrease",
    "v2_fixed_born_checkpoint_restart_exact",
)
FAIL_CLOSED_CASES = {
    "checkpoint_topology_crosswire": "checkpoint_topology_fingerprint_mismatch",
    "checkpoint_parameter_crosswire": "checkpoint_parameter_fingerprint_mismatch",
    "checkpoint_solvation_crosswire": (
        "checkpoint_solvation_parameter_fingerprint_mismatch"
    ),
    "fixed_born_periodic_cell_rejected": "periodic_fixed_born_not_supported",
    "line_search_budget_exhausted": "line_search_exhausted",
    "constraint_projection_budget_exhausted": ("constraint_projection_exhausted"),
}
CHECKPOINT_CASE_IDS = (
    "v1_checkpoint_restart_exact",
    "v2_constrained_checkpoint_restart_exact",
    "v2_fixed_born_checkpoint_restart_exact",
)


def _coordinates(result: object) -> tuple[tuple[float, float, float], ...]:
    tensor = result.system.coordinates[0]  # type: ignore[attr-defined]
    return tuple(tuple(float(value) for value in row) for row in tensor.tolist())


def test_all_frozen_cases_bind_result_free_independent_inputs() -> None:
    protocol = cpu_minimization_validation_protocol_document()
    manifest = cpu_minimization_validation_materialization_manifest_document()
    assert len(manifest["cases"]) == 14
    assert manifest["independent_minimization_reference_implemented"] is True
    for protocol_row, materialized_row in zip(
        protocol["case_manifest"]["cases"], manifest["cases"], strict=True
    ):
        case = materialize_frozen_cpu_minimization_validation_case(
            protocol_row["case_id"]
        )
        assert case.independent_oracle_input.case_id == case.case_id
        assert case.independent_oracle_input.case_input_sha256 == case.case_input_sha256
        assert materialized_row["independent_oracle_input_sha256"] == (
            case.independent_oracle_input.input_sha256
        )
        assert materialized_row["minimization_executed"] is False
        assert materialized_row["validation_result_collected"] is False


@pytest.mark.parametrize("case_id", PASS_CASE_IDS)
def test_independent_reference_matches_operational_endpoint(case_id: str) -> None:
    case = materialize_frozen_cpu_minimization_validation_case(case_id)
    source = replace(
        case.independent_oracle_input,
        pause_after_accepted_iterations=None,
    )
    independent = evaluate_independent_minimization_oracle(source)
    if case.v2_parameters is None:
        operational = minimize_reference_force_field(
            case.system,
            case.base_parameters,
            case.minimization_config,
        )
        operational_force = operational.final_max_force_kcal_per_mol_angstrom
    else:
        assert case.constrained_config is not None
        operational = minimize_reference_force_field_v2_constrained(
            case.system,
            case.v2_parameters,
            case.constrained_config,
            solvation_parameters=case.solvation_parameters,
        )
        operational_force = operational.final_max_tangent_force_kcal_per_mol_angstrom
    assert independent.status == operational.status
    assert independent.failure_code == operational.failure_code
    assert independent.accepted_iterations == operational.accepted_iterations
    assert independent.rejected_evaluations == operational.rejected_evaluations
    assert independent.evaluation_count == operational.evaluation_count
    assert independent.final_coordinates_angstrom is not None
    coordinate_error = max(
        abs(reference - candidate)
        for reference_row, candidate_row in zip(
            independent.final_coordinates_angstrom,
            _coordinates(operational),
            strict=True,
        )
        for reference, candidate in zip(reference_row, candidate_row, strict=True)
    )
    assert coordinate_error <= 1.0e-8
    assert independent.final_energy_kcal_per_mol is not None
    assert (
        abs(
            independent.final_energy_kcal_per_mol
            - operational.final_energy_kcal_per_mol
        )
        <= 1.0e-10
    )
    assert independent.final_max_force_kcal_per_mol_angstrom is not None
    assert (
        abs(independent.final_max_force_kcal_per_mol_angstrom - operational_force)
        <= 1.0e-8
    )
    assert independent.to_dict()["validation_receipt"] is False
    assert independent.to_dict()["scientifically_validated"] is False
    assert independent.to_dict()["claim_safe"] is False


@pytest.mark.parametrize("case_id", CHECKPOINT_CASE_IDS)
def test_checkpoint_resume_is_exact_for_independent_reference(case_id: str) -> None:
    case = materialize_frozen_cpu_minimization_validation_case(case_id)
    uninterrupted_source = replace(
        case.independent_oracle_input,
        pause_after_accepted_iterations=None,
    )
    uninterrupted = evaluate_independent_minimization_oracle(uninterrupted_source)
    paused = evaluate_independent_minimization_oracle(case.independent_oracle_input)
    assert paused.status == "checkpointed"
    assert paused.checkpoint is not None
    resumed = evaluate_independent_minimization_oracle(
        uninterrupted_source,
        checkpoint=paused.checkpoint,
    )
    assert resumed.result_sha256 == uninterrupted.result_sha256
    assert resumed.checkpoint is not None
    assert uninterrupted.checkpoint is not None
    assert (
        resumed.checkpoint.checkpoint_sha256
        == uninterrupted.checkpoint.checkpoint_sha256
    )


@pytest.mark.parametrize("case_id,error_code", FAIL_CLOSED_CASES.items())
def test_frozen_negative_cases_fail_closed_with_exact_code(
    case_id: str,
    error_code: str,
) -> None:
    case = materialize_frozen_cpu_minimization_validation_case(case_id)
    result = evaluate_independent_minimization_oracle(case.independent_oracle_input)
    assert result.status == "fail_closed"
    assert result.failure_code == error_code
    assert result.converged is False
    if case_id == "line_search_budget_exhausted":
        assert result.evaluation_count > 0
        assert result.rejected_evaluations > 0
        assert result.final_coordinates_angstrom is not None
        assert result.accepted_energy_trace_kcal_per_mol
    else:
        assert result.checkpoint is None


def test_checkpoint_digest_and_compatibility_fail_closed() -> None:
    case = materialize_frozen_cpu_minimization_validation_case(
        "v1_checkpoint_restart_exact"
    )
    paused = evaluate_independent_minimization_oracle(case.independent_oracle_input)
    assert paused.checkpoint is not None
    with pytest.raises(
        IndependentMinimizationOracleError,
        match="checkpoint compatibility identity mismatch",
    ):
        evaluate_independent_minimization_oracle(
            replace(
                case.independent_oracle_input,
                max_iterations=63,
                pause_after_accepted_iterations=None,
            ),
            checkpoint=paused.checkpoint,
        )


def test_import_boundary_excludes_operational_and_third_party_modules() -> None:
    source_path = Path(
        __import__(
            "betelgeuze_engine_v2.physics.reference_minimization_independent_oracle",
            fromlist=["__file__"],
        ).__file__
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert imports == {
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "math",
        "numbers",
        "typing",
        "reference_validation_oracle",
    }
    for forbidden in (
        "torch",
        "numpy",
        "reference_forcefield",
        "reference_forcefield_v2",
        "reference_minimization",
        "reference_constrained_minimization",
        "reference_solvation",
        "reference_minimization_validation_materializer",
        "reference_minimization_validation_protocol",
    ):
        assert forbidden not in imports
    assert "__import__" not in source
    assert "importlib" not in source
