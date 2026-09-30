"""Analytic repeated-step invariants, publication commits, and bounded failures."""
import copy
import json

import numpy as np
import pytest
import torch

from docs.research.human_5ht6_d3_complex import feasible_trajectory_core as core


def valid(_):
    return {"complete": True, "valid": True,
            "details": {"chiral_checks": [True] * 8, "double_bond_checks": [True] * 6}}


def linear(xyz):
    gradient = torch.zeros_like(xyz)
    gradient[0, 0] = -1
    energy = -float(xyz[0, 0])
    return energy, gradient, 0., torch.zeros_like(xyz), {"total": energy}


def quadratic(xyz, target):
    delta = xyz.clone()
    delta[0, 0] -= target
    energy = float(delta.square().sum())
    return energy, 2 * delta, 0., torch.zeros_like(xyz), {"total": energy}


def execute(objective=linear, validity=valid, record=None, original=None, bonds=(), **kwargs):
    rows = []
    original = torch.zeros(1, 3, dtype=torch.float64) if original is None else original
    final, report = core.feasible_armijo_trajectory(
        original, bonds, objective, validity, rows.append if record is None else record, **kwargs)
    json.dumps(report, allow_nan=False)
    return final, report, rows


def test_cumulative_strain_never_rebases_and_later_blocking_retains_first_step():
    def objective(xyz):
        energy, gradient, _, internal_gradient, components = linear(xyz)
        internal_gradient[0, 0] = 100
        return energy, gradient, 100 * float(xyz[0, 0]), internal_gradient, components
    final, report, _ = execute(objective)
    assert float(final[0, 0]) == .05
    assert report["accepted_steps"] == report["trusted_accepted_steps"] == 1
    assert report["accepted_objective_point_attempts"] == [2]
    assert report["termination"] == "backtracking_blocked"
    assert report["counters"]["objective_point_attempts"] == 18
    assert report["final"]["internal_increase_from_original_kcal_mol"] == 5
    assert all(row["internal_increase_from_original_kcal_mol"] > 5 for row in report["attempts"][2:])
    assert all(not row["checks"]["strain_within_exact_limit"] for row in report["attempts"][2:])
    assert report["counters"]["validity_calls"] == 18


def test_cumulative_original_bond_drift_is_not_reset_by_accepted_steps():
    original = torch.tensor([[0., 0., 0.], [1., 0., 0.]], dtype=torch.float64)
    final, report, _ = execute(original=original, bonds=((0, 1),))
    assert report["accepted_steps"] > 1
    assert report["original_bond_lengths_angstrom"] == [1.]
    assert 0 < float(final[0, 0]) <= .15
    for row in report["attempts"]:
        if row.get("eligible"):
            length = np.linalg.norm(np.asarray(row["coordinates_angstrom"])[0] - np.asarray(row["coordinates_angstrom"])[1])
            assert abs(length - 1.) <= .15
            assert row["original_bond_length_changes_angstrom"] == pytest.approx([length - 1.])
    assert any(not row["checks"]["original_bonds_within_exact_limit"] for row in report["attempts"][1:])


def test_direction_rotates_with_current_gradient_instead_of_initial_gradient():
    def anisotropic(xyz):
        x, y = xyz[0, :2]
        energy = float((x - 1)**2 + 4 * (y - .2)**2)
        gradient = torch.tensor([[2 * (x - 1), 8 * (y - .2), 0]], dtype=torch.float64)
        return energy, gradient, 0., torch.zeros_like(xyz), {"total": energy}
    _, report, _ = execute(anisotropic, protocol={"max_accepted_steps": 3})
    assert report["accepted_steps"] == 3
    first_direction = np.array(report["steps"][0]["direction"])
    assert not np.allclose(first_direction, report["steps"][1]["direction"])
    by_id = {row["objective_point_attempt"]: row for row in report["attempts"]}
    for step in report["steps"]:
        base = by_id[step["base_objective_point_attempt"]]
        gradient = np.array(base["total_gradient_kcal_mol_angstrom"])
        expected = -gradient / np.linalg.norm(gradient, axis=1).max()
        np.testing.assert_allclose(step["direction"], expected, rtol=0, atol=1e-15)
        assert step["base_gradient_dot_direction"] == pytest.approx(float((gradient * expected).sum()))


def test_current_armijo_rejects_insufficient_decrease_below_original_energy():
    final, report, _ = execute(lambda xyz: quadratic(xyz, .0750005))
    assert report["accepted_objective_point_attempts"] == [2, 4]
    rejected = report["attempts"][2]
    base = report["attempts"][1]
    assert rejected["armijo_base_objective_point_attempt"] == 2
    assert rejected["total_energy_kcal_mol"] < base["total_energy_kcal_mol"] < report["initial"]["total_energy_kcal_mol"]
    assert rejected["checks"]["strict_total_energy_decrease"]
    assert not rejected["checks"]["armijo_sufficient_decrease"]
    assert rejected["armijo_upper_bound_kcal_mol"] == pytest.approx(base["total_energy_kcal_mol"] - 1e-4 * .05 * .050001)
    assert float(final[0, 0]) == pytest.approx(.075)
    assert report["termination"] == "raw_force_tolerance_met" and report["raw_force_converged"]
    assert report["product_status"] == "NOT_ADMITTED" and not report["convergence_claimed"]


def test_current_strict_decrease_rejects_trial_lower_than_original_but_above_incumbent():
    _, report, _ = execute(lambda xyz: quadratic(xyz, .055), protocol={"max_accepted_steps": 2})
    trial = report["attempts"][2]
    assert trial["total_energy_kcal_mol"] < report["initial"]["total_energy_kcal_mol"]
    assert trial["total_energy_kcal_mol"] > report["attempts"][1]["total_energy_kcal_mol"]
    assert not trial["checks"]["strict_total_energy_decrease"]
    assert all(row["checks"]["distinct_current_coordinates"] for row in report["attempts"][1:])


@pytest.mark.parametrize("stage", ["objective", "validity", "malformed", "point_record", "step_record"])
def test_later_failure_retains_only_last_successfully_step_published_incumbent(stage):
    def objective(xyz):
        if float(xyz[0, 0]) > .05:
            if stage == "objective":
                raise RuntimeError("later native failure")
            if stage == "malformed":
                values = list(linear(xyz))
                values[1][0, 0] = float("nan")
                return tuple(values)
        return linear(xyz)
    def validity(xyz):
        if stage == "validity" and float(xyz[0, 0]) > .05:
            raise RuntimeError("later geometry failure")
        return valid(xyz)
    def record(row):
        if stage == "point_record" and row["event"] == "objective_point" and row["objective_point_attempt"] == 3:
            raise OSError("later point cannot publish")
        if stage == "step_record" and row["event"] == "trajectory_step_selection" and row["step_index"] == 2:
            raise OSError("later selection cannot publish")
    final, report, _ = execute(objective, validity, record)
    assert float(final[0, 0]) == .05
    assert report["accepted_steps"] == 1 and report["accepted_objective_point_attempts"] == [2]
    assert report["retained_objective_point_attempt"] == 2
    assert report["termination"] == "evaluation_or_callback_failure"
    assert not report["raw_force_converged"]
    assert report["counters"]["objective_point_attempts"] == 3
    assert not report["steps"][-1]["published"]
    assert report["counters"]["validity_calls"] == (2 if stage == "objective" else 3)
    if stage == "malformed":
        assert report["attempts"][-1]["full_validity"]["complete"]
        assert report["counters"]["invalid_objective_results"] == 1
    if stage == "step_record":
        assert report["steps"][-1]["proposed_accepted_objective_point_attempt"] == 3
        assert report["steps"][-1]["accepted_objective_point_attempt"] is None
        assert report["publications"][-1]["event"]["event"] == "trajectory_step_selection"
        assert not report["publications"][-1]["succeeded"]


def test_later_sixteen_geometry_rejections_keep_published_intermediate_and_reset_alpha():
    final, report, _ = execute(validity=lambda xyz: {"complete": True, "valid": float(xyz[0, 0]) <= .05})
    assert float(final[0, 0]) == .05 and report["accepted_steps"] == 1
    assert report["termination"] == "backtracking_blocked"
    assert [row["alpha_angstrom"] for row in report["attempts"][2:]] == [.05 * .5**j for j in range(16)]
    assert report["counters"]["completed_objective_calls"] == report["counters"]["validity_calls"] == 18
    assert [row["step_index"] for row in report["attempts"]] == [None, 1] + [2] * 16


def test_global_budget_counts_initial_rejected_and_successful_native_points():
    calls = [0]
    def validity(xyz):
        calls[0] += 1
        return {"complete": True, "valid": (calls[0] - 1) % 5 == 0}
    _, report, _ = execute(validity=validity)
    assert report["termination"] == "objective_point_budget_exhausted"
    assert report["counters"]["objective_point_attempts"] == report["counters"]["objective_calls"] == 129
    assert report["counters"]["backtracking_trials_attempted"] == 128
    assert report["accepted_steps"] == 25
    assert len(report["steps"][-1]["trial_objective_point_attempts"]) == 3
    assert len(report["attempts"]) == 129


def test_default_accepted_step_budget_stops_at_32_with_no_terminal_re_evaluation():
    final, report, _ = execute()
    assert float(final[0, 0]) == pytest.approx(1.6)
    assert report["termination"] == "accepted_step_budget_exhausted"
    assert report["accepted_steps"] == 32
    assert report["counters"]["objective_calls"] == 33


@pytest.mark.parametrize("points,expected", [(1, 1), (2, 2), (4, 4)])
def test_reduced_global_budget_stops_without_extra_native_point(points, expected):
    _, report, _ = execute(protocol={"max_objective_point_attempts": points})
    assert report["termination"] == "objective_point_budget_exhausted"
    assert report["counters"]["objective_point_attempts"] == expected
    assert report["accepted_steps"] == points - 1


def test_reduced_per_step_budget_and_initial_infeasibility():
    _, blocked, _ = execute(validity=lambda xyz: {"complete": True, "valid": float(xyz[0, 0]) == 0},
                            protocol={"max_backtracking_trials": 2})
    assert blocked["termination"] == "backtracking_blocked" and len(blocked["attempts"]) == 3
    _, initial, _ = execute(validity=lambda _: {"complete": True, "valid": False})
    assert initial["termination"] == "initial_not_fully_feasible"
    assert len(initial["attempts"]) == 1 and initial["steps"] == [] and not initial["raw_force_converged"]


@pytest.mark.parametrize("target", [0., 1e-8, .0005])
def test_initial_raw_force_tolerance_is_separate_from_energy_lowering_and_admission(target):
    final, report, _ = execute(lambda xyz: quadratic(xyz, target))
    assert torch.count_nonzero(final) == 0
    assert report["termination"] == "raw_force_tolerance_met" and report["raw_force_converged"]
    assert report["accepted_steps"] == 0 and report["counters"]["objective_calls"] == 1
    assert report["product_status"] == "NOT_ADMITTED" and not report["convergence_claimed"]


def test_stagnation_is_not_raw_force_convergence():
    def rounded(xyz):
        values = linear(xyz)
        return 1e16 + values[0], *values[1:]
    final, report, _ = execute(rounded)
    assert torch.count_nonzero(final) == 0 and not report["raw_force_converged"]
    assert report["termination"] == "backtracking_blocked" and len(report["attempts"]) == 17


def test_final_publication_failure_retains_completed_commit_but_never_converges():
    def plateau(xyz):
        values = list(linear(xyz))
        if float(xyz[0, 0]) >= .05:
            values[1].zero_()
        return tuple(values)
    def record(row):
        if row["event"] == "trajectory_selection":
            raise OSError("final report failed")
    final, report, _ = execute(plateau, record=record)
    assert float(final[0, 0]) == .05 and report["accepted_steps"] == 1
    assert report["final"]["raw_maximum_atom_force_kcal_mol_angstrom"] == 0
    assert report["termination"] == "evaluation_or_callback_failure" and not report["raw_force_converged"]


@pytest.mark.parametrize("stage", ["objective", "validity", "record"])
def test_sticky_source_integrity_revokes_all_historical_accepted_selection(stage):
    source_ok = [True]
    def intact():
        if not source_ok[0]:
            source_ok[0] = True
            raise RuntimeError("source changed then restored")
    def objective(xyz):
        if stage == "objective" and float(xyz[0, 0]) > .05:
            source_ok[0] = False
            raise RuntimeError("native failure does not hide integrity")
        return linear(xyz)
    def validity(xyz):
        if stage == "validity" and float(xyz[0, 0]) > .05:
            source_ok[0] = False
        return valid(xyz)
    def record(row):
        if stage == "record" and row["event"] == "trajectory_step_selection" and row["step_index"] == 2:
            source_ok[0] = False
    final, report, _ = execute(objective, validity, record, intact=intact)
    assert torch.count_nonzero(final) == 0 and source_ok[0]
    assert report["accepted_steps"] == 1 and report["accepted_objective_point_attempts"] == [2]
    assert report["trusted_accepted_steps"] == 0 and report["selection_revoked"]
    assert report["retained_objective_point_attempt"] == 1
    assert report["termination"] == "source_integrity_failure" and not report["raw_force_converged"]


@pytest.mark.parametrize("stage", ["objective", "validity"])
def test_mutated_trial_coordinate_argument_after_commit_revokes_selection(stage):
    def callback(xyz):
        if float(xyz[0, 0]) > .05:
            xyz[0, 0] = 999
        return linear(xyz) if stage == "objective" else valid(xyz)
    final, report, _ = execute(callback if stage == "objective" else linear,
                               callback if stage == "validity" else valid)
    assert torch.count_nonzero(final) == 0
    assert report["accepted_steps"] == 1 and not report["source_integrity_valid"]
    assert "mutated_coordinate_argument" in report["integrity_error"]


def test_record_copy_isolation_and_chronological_publication_commit_chain():
    emitted = []
    def record(row):
        emitted.append(copy.deepcopy(row))
        if "coordinates_angstrom" in row:
            row["coordinates_angstrom"][0][0] = 999
    final, report, _ = execute(record=record, protocol={"max_accepted_steps": 2})
    assert float(final[0, 0]) == .1
    assert [row["objective_point_attempt"] for row in report["attempts"]] == [1, 2, 3]
    assert [p["publication_index"] for p in report["publications"]] == list(range(1, 7))
    assert [p["event"] for p in report["publications"]] == emitted
    assert report["accepted_objective_point_attempts"] == [2, 3]
    assert report["counters"]["record_calls"] == 6
    assert all(row["counter_delta"]["objective_calls"] == 1 for row in report["attempts"])
    for step in report["steps"]:
        publication = report["publications"][step["publication_index"] - 1]
        assert step["published"] and publication["succeeded"]
        assert publication["event"]["selected_objective_point_attempt"] == step["accepted_objective_point_attempt"]


@pytest.mark.parametrize("protocol", [
    {"max_accepted_steps": 33}, {"max_accepted_steps": True}, {"max_accepted_steps": 0},
    {"max_backtracking_trials": 17}, {"max_objective_point_attempts": 130},
    {"armijo_c1": 0.}, {"internal_increase_limit_kcal_mol": 5.1},
    {"original_bond_length_change_limit_angstrom": .151}, {"initial_alpha_angstrom": .1},
    {"raw_maximum_atom_force_tolerance_kcal_mol_angstrom": .01}, {"unknown": 1},
])
def test_protocol_cannot_extend_budgets_or_relax_constraints(protocol):
    with pytest.raises(ValueError):
        execute(protocol=protocol)
