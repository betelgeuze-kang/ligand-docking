"""Energy-based bounded local refinement tests (P1-6)."""

from __future__ import annotations

import numpy as np

from betelgeuze_engine.scoring.local_refinement import (
    LOCAL_REFINEMENT_SCHEMA_VERSION,
    METHOD,
    STATUS_FAILED,
    STATUS_NO_IMPROVEMENT,
    TERMINAL_STATUSES,
    RefinementParameters,
    refine_pose_locally,
)

PROTEIN = np.asarray(
    [
        [0.0, 0.0, 0.0],
        [4.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [0.0, 0.0, 4.0],
        [4.0, 4.0, 4.0],
        [2.0, 2.0, 6.0],
    ],
    dtype=np.float64,
)
LIGAND = np.asarray([[2.2, 2.0, 2.0], [2.9, 2.0, 2.0]], dtype=np.float64)


def _refine(**overrides):
    kwargs = {
        "protein_elements": ["C"] * 6,
        "ligand_elements": ["C", "O"],
        "ligand_smiles": "CCO",
        "pocket_center": [2.0, 2.0, 2.0],
        "pocket_radius_a": 6.0,
    }
    kwargs.update(overrides)
    protein = kwargs.pop("protein_xyz", PROTEIN)
    ligand = kwargs.pop("ligand_xyz", LIGAND)
    return refine_pose_locally(protein, ligand, **kwargs)


def test_refinement_reports_a_terminal_status() -> None:
    result = _refine()

    assert result.status in TERMINAL_STATUSES
    assert result.to_dict()["schema_version"] == LOCAL_REFINEMENT_SCHEMA_VERSION
    assert result.to_dict()["method"] == METHOD


def test_refinement_improves_or_leaves_the_score_unchanged() -> None:
    result = _refine()

    # Refinement must never make the pose worse than where it started.
    assert result.post_score <= result.pre_score + 1e-9
    assert result.score_delta <= 1e-9


def test_score_delta_matches_pre_and_post_scores() -> None:
    result = _refine()

    assert abs(result.score_delta - (result.post_score - result.pre_score)) < 1e-12


def test_pre_and_post_coordinates_are_both_recorded() -> None:
    result = _refine()
    payload = result.to_dict()

    assert len(payload["pre_coordinates"]) == LIGAND.shape[0]
    assert len(payload["post_coordinates"]) == LIGAND.shape[0]
    assert payload["pre_coordinates"] == [
        [round(float(v), 4) for v in row] for row in LIGAND
    ]


def test_displacement_stays_within_the_configured_bound() -> None:
    params = RefinementParameters(max_displacement_a=0.3, max_steps=40)
    result = _refine(parameters=params)
    payload = result.to_dict()

    assert result.max_atom_displacement_a <= 0.3 + 1e-6
    assert payload["displacement_within_bound"] is True
    assert payload["max_displacement_bound_a"] == 0.3


def test_tighter_bound_permits_less_movement() -> None:
    loose = _refine(parameters=RefinementParameters(max_displacement_a=1.5, max_steps=40))
    tight = _refine(parameters=RefinementParameters(max_displacement_a=0.1, max_steps=40))

    assert tight.max_atom_displacement_a <= loose.max_atom_displacement_a + 1e-9
    assert tight.max_atom_displacement_a <= 0.1 + 1e-6


def test_zero_step_budget_yields_no_improvement_and_no_movement() -> None:
    result = _refine(parameters=RefinementParameters(max_steps=0))

    assert result.steps_taken == 0
    assert result.max_atom_displacement_a == 0.0
    assert result.post_score == result.pre_score
    assert result.improved is False


def test_parameter_identity_is_recorded_and_deterministic() -> None:
    params = RefinementParameters(max_steps=8, translation_step_a=0.15)
    first = _refine(parameters=params).to_dict()
    second = _refine(parameters=params).to_dict()

    assert first["parameters"]["max_steps"] == 8
    assert first["parameters"]["translation_step_a"] == 0.15
    assert first["parameters"]["method"] == METHOD
    assert first["parameter_digest"] == second["parameter_digest"]


def test_different_parameters_produce_a_different_digest() -> None:
    a = RefinementParameters(max_steps=8).parameter_digest
    b = RefinementParameters(max_steps=9).parameter_digest

    assert a != b


def test_refinement_is_deterministic() -> None:
    first = _refine()
    second = _refine()

    assert first.post_score == second.post_score
    assert first.post_coordinates == second.post_coordinates


def test_convergence_is_reported_explicitly() -> None:
    result = _refine(parameters=RefinementParameters(max_steps=200))
    payload = result.to_dict()

    assert isinstance(payload["converged"], bool)
    assert payload["converged"] == (result.status == "local_refinement_converged")


def test_missing_coordinates_produce_a_failure_row() -> None:
    result = _refine(protein_xyz=np.zeros((0, 3)))
    payload = result.to_dict()

    assert result.status == STATUS_FAILED
    assert result.failed is True
    assert payload["failure_reason"] == "refinement_requires_protein_and_ligand_coordinates"
    assert payload["blockers"] == ["refinement_requires_protein_and_ligand_coordinates"]
    # A failure row still carries the parameter identity for the denominator.
    assert payload["parameter_digest"]


def test_already_optimal_pose_reports_no_improvement_or_converged() -> None:
    result = _refine(
        parameters=RefinementParameters(
            max_steps=40, translation_step_a=1e-9, rotation_step_rad=1e-9
        )
    )

    assert result.status in {STATUS_NO_IMPROVEMENT, "local_refinement_converged"}
    assert result.max_atom_displacement_a < 1e-3


def test_payload_states_uncalibrated_refinement_boundary() -> None:
    payload = _refine().to_dict()

    assert "uncalibrated" in payload["claim_boundary"]
    assert "not an energy minimization claim" in payload["claim_boundary"]
