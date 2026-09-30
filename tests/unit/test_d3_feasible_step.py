"""Analytic nonlinear backtracking and failure/receipt boundary checks."""
import copy
import json

import numpy as np
import pytest
import torch

from docs.research.human_5ht6_d3_complex import feasible_step_core as core


def valid(_):
    return {"complete": True, "valid": True, "details": {"synthetic_geometry": True}}


def quadratic(xyz, target=1.0, strain_weight=0.0):
    target_xyz = torch.zeros_like(xyz)
    target_xyz[0, 0] = target
    energy = float((xyz - target_xyz).square().sum())
    internal = float(strain_weight * xyz.square().sum())
    return (energy, 2 * (xyz - target_xyz), internal, 2 * strain_weight * xyz,
            {"total": energy, "ligand_internal": internal})


def run(objective=quadratic, validity=valid, **kwargs):
    rows = []
    final, report = core.feasible_armijo_step(torch.zeros(1, 3, dtype=torch.float64), (),
                                            objective, validity, rows.append, **kwargs)
    json.dumps(report, allow_nan=False)
    return final, report, rows


def test_actual_nonlinear_strain_forces_shorter_step_and_stops_first_eligible():
    seen = []
    def objective(xyz):
        seen.append(float(xyz[0, 0]))
        return quadratic(xyz, strain_weight=10000.0)
    final, report, rows = run(objective)
    assert seen == [0.0, .05, .025, .0125]
    assert float(final[0, 0]) == .0125
    assert report["step_accepted"] and report["accepted_trial_index"] == 2
    assert report["termination"] == "first_feasible_armijo_step"
    assert [r["outcome"] for r in report["attempts"]] == ["initial_feasible", "rejected", "rejected", "accepted"]
    assert [r["internal_energy_kcal_mol"] for r in report["attempts"]] == pytest.approx([0, 25, 6.25, 1.5625])
    assert report["final"]["total_energy_kcal_mol"] == pytest.approx((1 - .0125)**2)
    assert report["final"]["total_gradient_kcal_mol_angstrom"] == [[-1.975, 0., 0.]]
    assert report["final"]["internal_gradient_kcal_mol_angstrom"] == [[250., 0., 0.]]
    assert report["counters"]["validity_calls"] == report["counters"]["completed_objective_calls"] == 4
    assert len([row for row in rows if row["event"] == "objective_point"]) == 4
    assert not report["raw_force_converged"] and not report["convergence_claimed"]
    assert report["product_status"] == "NOT_ADMITTED"


def test_armijo_rejects_actual_decrease_that_is_too_small():
    final, report, _ = run(lambda xyz: quadratic(xyz, target=.0250005))
    first = report["attempts"][1]
    assert first["checks"]["strict_total_energy_decrease"]
    assert not first["checks"]["armijo_sufficient_decrease"]
    assert first["total_energy_kcal_mol"] > first["armijo_upper_bound_kcal_mol"]
    assert float(final[0, 0]) == .025 and report["accepted_trial_index"] == 1
    assert report["counters"]["objective_point_attempts"] == 3


@pytest.mark.parametrize("field", ["complete", "valid"])
def test_all_rejected_completed_points_get_geometry_and_first_valid_point_wins(field):
    seen = []
    def validity(xyz):
        x = float(xyz[0, 0])
        seen.append(x)
        result = valid(xyz)
        result[field] = x <= .02
        return result
    final, report, _ = run(validity=validity)
    assert seen == [0., .05, .025, .0125]
    assert float(final[0, 0]) == .0125
    assert all(not row["checks"]["complete_full_validity"] for row in report["attempts"][1:3])


def test_all_sixteen_real_quadratic_trials_can_fail_and_original_is_retained():
    final, report, _ = run(lambda xyz: quadratic(xyz, target=1e-8))
    assert torch.count_nonzero(final) == 0 and not report["step_accepted"]
    assert report["termination"] == "backtracking_exhausted"
    assert report["counters"]["objective_point_attempts"] == 17
    assert report["counters"]["backtracking_trials_attempted"] == 16
    assert report["counters"]["validity_calls"] == 17
    assert [row["alpha_angstrom"] for row in report["attempts"][1:]] == [.05 * 2**-j for j in range(16)]
    assert report["raw_force_converged"]  # Separate from actual energy lowering.
    assert report["product_status"] == "NOT_ADMITTED"
    assert all(not row["checks"]["strict_total_energy_decrease"] for row in report["attempts"][1:])


def test_rounded_energy_equality_never_counts_as_useful_decrease():
    def objective(xyz):
        values = quadratic(xyz, target=.01)
        return 1e16 + values[0], *values[1:]
    final, report, _ = run(objective)
    assert not report["step_accepted"] and torch.count_nonzero(final) == 0
    assert all(not row["checks"]["strict_total_energy_decrease"] for row in report["attempts"][1:])


@pytest.mark.parametrize("budget,expected", [(1, 1), (3, 3)])
def test_smaller_point_budget_charges_initial_and_every_failed_candidate(budget, expected):
    final, report, _ = run(lambda xyz: quadratic(xyz, target=1e-8),
                           protocol={"max_objective_point_attempts": budget})
    assert report["termination"] == "objective_point_budget_exhausted"
    assert report["counters"]["objective_point_attempts"] == expected
    assert report["counters"]["validity_calls"] == expected
    assert torch.count_nonzero(final) == 0


def test_reduced_trial_budget_has_no_extra_terminal_evaluation():
    _, report, _ = run(lambda xyz: quadratic(xyz, target=1e-8), protocol={"max_backtracking_trials": 2})
    assert report["termination"] == "backtracking_exhausted"
    assert report["counters"]["objective_calls"] == 3


def test_zero_gradient_has_no_trial_or_division_by_zero():
    final, report, _ = run(lambda xyz: quadratic(xyz, target=0))
    assert torch.count_nonzero(final) == 0
    assert report["termination"] == "zero_original_gradient" and report["direction"] is None
    assert report["counters"]["objective_calls"] == report["counters"]["validity_calls"] == 1
    assert report["raw_force_converged"] and not report["step_accepted"]
    assert report["product_status"] == "NOT_ADMITTED"


def test_direction_uses_original_maximum_atom_norm_and_records_exact_bond_metrics():
    original = torch.tensor([[0., 0., 0.], [1., .4, -.3]], dtype=torch.float64)
    gradient = torch.tensor([[-3., -4., 0.], [-1., 0., 0.]], dtype=torch.float64)
    def linear(xyz):
        energy = float((gradient * xyz).sum())
        return energy, gradient.clone(), 0., torch.zeros_like(xyz), {"total": energy}
    final, report = core.feasible_armijo_step(original, ((0, 1),), linear, valid, lambda _: None)
    expected = original + .05 * (-gradient / 5)
    torch.testing.assert_close(final, expected, atol=0, rtol=0)
    np.testing.assert_allclose(report["direction"], -gradient.numpy() / 5, atol=0, rtol=0)
    assert report["original_gradient_dot_direction"] == pytest.approx(-26 / 5)
    change = float(torch.linalg.vector_norm(final[0] - final[1]) - torch.linalg.vector_norm(original[0] - original[1]))
    assert report["final"]["original_bond_length_changes_angstrom"] == pytest.approx([change])
    assert report["final"]["maximum_original_bond_length_change_angstrom"] == pytest.approx(abs(change))
    assert report["final"]["checks"]["original_bonds_within_exact_limit"]
    assert not torch.equal(original, final)


@pytest.mark.parametrize("where", ["initial", "trial"])
@pytest.mark.parametrize("bad", ["energy_nan", "gradient_nan", "internal_inf", "wrong_gradient_dtype", "malformed"])
def test_completed_but_bad_numerical_result_still_gets_geometry_without_fake_energy(where, bad):
    def objective(xyz):
        if (float(xyz[0, 0]) == 0) != (where == "initial"):
            return quadratic(xyz)
        value = list(quadratic(xyz))
        if bad == "energy_nan":
            value[0] = float("nan")
        elif bad == "gradient_nan":
            value[1][0, 0] = float("nan")
        elif bad == "internal_inf":
            value[2] = float("inf")
        elif bad == "wrong_gradient_dtype":
            value[1] = value[1].float()
        else:
            return (value[0],)
        return tuple(value)
    final, report, _ = run(objective)
    expected = 1 if where == "initial" else 2
    assert report["counters"]["completed_objective_calls"] == expected
    assert report["counters"]["validity_calls"] == expected
    assert report["counters"]["invalid_objective_results"] == 1
    assert report["counters"]["failed_objective_calls"] == 0
    assert report["attempts"][-1]["full_validity"]["complete"]
    assert "total_energy_kcal_mol" not in report["attempts"][-1]
    assert not report["step_accepted"] and torch.count_nonzero(final) == 0
    assert report["termination"] == "evaluation_or_callback_failure"


@pytest.mark.parametrize("stage", ["objective", "validity"])
@pytest.mark.parametrize("where", ["initial", "trial"])
def test_failed_callbacks_are_charged_separately_and_fatal(stage, where):
    def fail(xyz):
        if (float(xyz[0, 0]) == 0) == (where == "initial"):
            raise RuntimeError("synthetic callback failure")
        return quadratic(xyz) if stage == "objective" else valid(xyz)
    final, report, _ = run(fail if stage == "objective" else quadratic,
                           fail if stage == "validity" else valid)
    attempted = 1 if where == "initial" else 2
    assert report["counters"]["objective_point_attempts"] == attempted
    assert report["counters"]["failed_" + stage + "_calls"] == 1
    assert report["counters"]["completed_objective_calls"] == attempted - (stage == "objective")
    assert report["counters"]["validity_calls"] == attempted - (stage == "objective")
    assert report["attempts"][-1]["outcome"] == "evaluation_failure"
    assert not report["step_accepted"] and torch.count_nonzero(final) == 0
    assert report["error"]["stage"] == stage
    if stage == "validity":
        assert "total_energy_kcal_mol" in report["attempts"][-1]
    else:
        assert "total_energy_kcal_mol" not in report["attempts"][-1]


@pytest.mark.parametrize("value", [{}, {"complete": 1, "valid": True}, {"complete": True, "valid": None}, None])
def test_malformed_validity_cannot_admit_a_point(value):
    final, report, _ = run(validity=lambda _: value)
    assert not report["step_accepted"] and torch.count_nonzero(final) == 0
    assert report["error"]["stage"] == "validity_result"


def test_initial_infeasibility_stops_before_any_trial():
    final, report, _ = run(validity=lambda _: {"complete": True, "valid": False})
    assert report["termination"] == "initial_not_fully_feasible"
    assert report["counters"]["objective_calls"] == 1 and not report["step_accepted"]
    assert torch.count_nonzero(final) == 0


@pytest.mark.parametrize("stage", ["objective", "validity", "record"])
@pytest.mark.parametrize("also_raise", [False, True])
def test_source_mutation_during_any_callback_is_sticky_and_revokes_selection(stage, also_raise):
    source_ok = [True]
    def intact():
        if not source_ok[0]:
            source_ok[0] = True  # Restoring bytes cannot erase an observed failure.
            raise RuntimeError("source changed then restored")
    def wrapped(value):
        if stage == "record":
            mutate = value["event"] == "single_step_selection"
        else:
            mutate = float(value[0, 0]) > 0
        if mutate:
            source_ok[0] = False
            if also_raise:
                raise RuntimeError("callback failure must not conceal source mutation")
        return quadratic(value) if stage == "objective" else valid(value)
    original = torch.zeros(1, 3, dtype=torch.float64)
    final, report = core.feasible_armijo_step(original, (), wrapped if stage == "objective" else quadratic,
        wrapped if stage == "validity" else valid, wrapped if stage == "record" else lambda _: None, intact=intact)
    assert source_ok[0]
    assert report["status"] == "INVALID_SOURCE_INTEGRITY" and not report["source_integrity_valid"]
    assert report["termination"] == "source_integrity_failure" and not report["step_accepted"]
    assert torch.equal(final, original)
    assert report["counters"]["failed_integrity_checks"] >= 1


@pytest.mark.parametrize("stage", ["objective", "validity"])
def test_callback_coordinate_argument_mutation_cannot_change_retained_snapshot(stage):
    def mutate(xyz):
        xyz[0, 0] += 1
        return quadratic(xyz) if stage == "objective" else valid(xyz)
    final, report, _ = run(mutate if stage == "objective" else quadratic,
                           mutate if stage == "validity" else valid)
    assert not report["source_integrity_valid"] and not report["step_accepted"]
    assert stage + "_mutated_coordinate_argument" in report["integrity_error"]
    assert torch.count_nonzero(final) == 0


def test_external_original_mutation_retains_pre_call_snapshot_and_is_invalid():
    original = torch.zeros(1, 3, dtype=torch.float64)
    def objective(xyz):
        original[0, 0] = 9
        return quadratic(xyz)
    final, report = core.feasible_armijo_step(original, (), objective, valid, lambda _: None)
    assert float(original[0, 0]) == 9 and torch.count_nonzero(final) == 0
    assert not report["source_integrity_valid"] and report["counters"]["validity_calls"] == 0


def test_record_copy_isolation_and_final_publication_failure_revoke_provisional_acceptance():
    rows = []
    def record(row):
        rows.append(copy.deepcopy(row))
        if row["event"] == "single_step_selection":
            raise OSError("ledger publication unavailable")
        row["coordinates_angstrom"][0][0] = 999
    original = torch.zeros(1, 3, dtype=torch.float64)
    final, report = core.feasible_armijo_step(original, (), quadratic, valid, record)
    assert report["attempts"][1]["coordinates_angstrom"][0][0] == .05
    assert report["attempts"][1]["eligible"]
    assert report["counters"]["failed_record_calls"] == 1 and not report["step_accepted"]
    assert report["final"]["coordinates_angstrom"] == [[0., 0., 0.]]
    assert torch.equal(final, original)


@pytest.mark.parametrize("protocol", [
    {"armijo_c1": 0.0}, {"internal_increase_limit_kcal_mol": 5.000001},
    {"original_bond_length_change_limit_angstrom": .151}, {"initial_alpha_angstrom": .1},
    {"max_backtracking_trials": 17}, {"max_objective_point_attempts": 18},
    {"max_objective_point_attempts": True}, {"max_backtracking_trials": 0}, {"extra": True},
])
def test_protocol_cannot_relax_thresholds_or_extend_frozen_search(protocol):
    with pytest.raises(ValueError):
        run(protocol=protocol)
