"""Analytic constrained minima, independent derivatives, and bounded execution."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from docs.research.human_5ht6_d3_complex import constrained_refinement_core as core


def valid(_):
    return {"complete": True, "valid": True, "fixture": "full_synthetic_validity"}


def objective(xyz):
    target = torch.tensor([[2., 0., 0.]], dtype=torch.float64)
    gradient = 2. * (xyz - target)
    energy = float((xyz - target).square().sum())
    internal_gradient = torch.zeros_like(xyz)
    internal_gradient[0, 0] = 10. * xyz[0, 0]
    internal = float(5. * xyz[0, 0].square())
    return energy, gradient, internal, internal_gradient, {"ligand_internal": internal, "total": energy}


def unconstrained_objective(xyz):
    target = torch.tensor([[2., 0., 0.]], dtype=torch.float64)
    energy = float((xyz - target).square().sum())
    return energy, 2. * (xyz - target), 0., torch.zeros_like(xyz), {"ligand_internal": 0., "total": energy}


def returned(xyz, success=True):
    return SimpleNamespace(x=np.asarray(xyz, dtype=np.float64).reshape(-1), success=success,
                           status=0 if success else 9, message="synthetic terminal", nit=1, nfev=1, njev=1)


def test_actual_slsqp_reaches_analytic_strain_boundary_but_never_raw_convergence():
    rows = []
    final, report, first = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), objective, valid, rows.append)
    assert float(final[0, 0]) == pytest.approx(1., abs=1e-5)
    assert report["final_admission"]["eligible"]
    assert report["kkt"]["stationary"] and report["constrained_stationary"]
    assert report["status"] == "CONSTRAINED_STATIONARY_ONLY"
    assert not report["raw_force_converged"] and report["product_status"] == "NOT_ADMITTED"
    assert report["final"]["raw_maximum_atom_force_kcal_mol_angstrom"] == pytest.approx(2., abs=2e-5)
    assert report["kkt"]["multipliers_kcal_mol"][0] == pytest.approx(1., abs=2e-5)
    assert first is not None
    assert report["counters"]["cache_hits"] > 0
    assert all(not row["is_slsqp_accepted_step_receipt"] for row in report["major_and_terminal_observations"])


def test_inactive_constraint_minimum_passes_independent_raw_and_kkt_gates():
    def f(xyz):
        target = torch.tensor([[.2, -.3, .1]], dtype=torch.float64)
        energy = float(500. * (xyz - target).square().sum())
        return energy, 1000. * (xyz - target), 0., torch.zeros_like(xyz), {"total": energy}
    final, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), f, valid, lambda _: None)
    torch.testing.assert_close(final, torch.tensor([[.2, -.3, .1]], dtype=torch.float64), atol=1e-12, rtol=0)
    assert report["status"] == "RAW_AND_CONSTRAINED_STATIONARY"
    assert report["kkt"]["active_constraint_indices"] == []
    assert not report["kkt"]["nnls_called"]
    assert report["raw_force_converged"]
    assert not report["product_qualified"]


def test_strain_and_bond_constraint_jacobians_match_independent_central_differences():
    xyz = np.array([[.2, -.3, .1], [1.3, .2, -.4], [.6, 1.4, .7]])
    bonds = ((0, 1), (1, 2))
    lengths = [np.linalg.norm(xyz[i] - xyz[j]) + .02 for i, j in bonds]
    weights = np.arange(1., 10.).reshape(3, 3) / 10.
    def observe(at):
        internal = float(np.sum(weights * at**2))
        return core.normalized_constraints(at, internal, 2. * weights * at, 1., bonds, lengths, core.PROTOCOL)
    values, jacobian, _ = observe(xyz)
    numerical = np.zeros_like(jacobian)
    h = 1e-6
    for index in range(xyz.size):
        plus, minus = xyz.copy(), xyz.copy()
        plus.flat[index] += h
        minus.flat[index] -= h
        numerical[:, index] = (observe(plus)[0] - observe(minus)[0]) / (2. * h)
    np.testing.assert_allclose(jacobian, numerical, atol=2e-9, rtol=0)
    np.testing.assert_allclose(jacobian[0], -(2. * weights * xyz).reshape(-1) / 5., atol=0, rtol=0)
    assert values.shape == (5,)


def make_boundary_point():
    cache = core.PointCache(torch.zeros(1, 3, dtype=torch.float64), (), objective, lambda _: None, lambda: None, core.PROTOCOL)
    cache.get(np.zeros(3), "initial")
    return cache.get(np.array([1., 0., 0.]), "boundary")


def test_exact_analytic_kkt_sign_and_units_with_nonzero_raw_gradient():
    point = make_boundary_point()
    report = core.kkt_audit(point, core.PROTOCOL)
    assert report["stationary"]
    assert report["multipliers_kcal_mol"] == [1.]
    assert report["raw_maximum_atom_force_kcal_mol_angstrom"] == 2.
    assert report["maximum_atom_residual_kcal_mol_angstrom"] == 0.
    assert report["maximum_complementarity_kcal_mol"] == 0.
    assert report["constraint_scope"] == "strain_and_original_bond_constraints_only"
    assert not report["objective_gradient_scaled"]


def test_even_tiny_negative_primal_slack_cannot_be_stationary():
    point = replace(make_boundary_point(), values=np.array([-1e-15]))
    report = core.kkt_audit(point, core.PROTOCOL)
    assert not report["primal_feasible_exact"] and not report["stationary"]
    assert report["maximum_normalized_primal_violation"] == 1e-15


@pytest.mark.parametrize("kind", ["raises", "negative", "nan"])
def test_nnls_failure_or_invalid_dual_never_claims_stationarity(kind):
    def solver(*args, **kwargs):
        if kind == "raises":
            raise RuntimeError("NNLS iterations exhausted")
        return np.array([-1. if kind == "negative" else float("nan")]), 0.
    report = core.kkt_audit(make_boundary_point(), core.PROTOCOL, nnls_solver=solver)
    assert not report["stationary"] and not report["dual_feasible_exact"]
    if kind != "negative":
        assert not report["nnls_succeeded"]


def test_inactive_normals_are_not_fitted_and_complementarity_is_unscaled():
    point = replace(make_boundary_point(), values=np.array([2e-6]))
    report = core.kkt_audit(point, core.PROTOCOL)
    assert not report["stationary"] and report["active_constraint_indices"] == []
    point = replace(make_boundary_point(), values=np.array([1e-6]), gradient=np.array([[-200., 0., 0.]]))
    report = core.kkt_audit(point, core.PROTOCOL)
    assert report["maximum_atom_residual_kcal_mol_angstrom"] == 0.
    assert report["maximum_complementarity_kcal_mol"] == pytest.approx(1e-4)
    assert not report["stationary"]


def test_192_point_budget_covers_all_trials_and_retains_only_observed_incumbent(monkeypatch):
    seen, rows = [], []
    def tracked(xyz):
        seen.append(xyz.clone())
        return unconstrained_objective(xyz)
    def optimizer(fun, x0, **kwargs):
        assert "bounds" not in kwargs
        fun(np.array([1., 0., 0.]))
        kwargs["callback"](np.array([1., 0., 0.]))
        for value in range(2, 300):
            fun(np.array([float(value), 0., 0.]))
        pytest.fail("point budget did not stop optimizer")
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), tracked, valid, rows.append)
    assert len(seen) == report["counters"]["objective_point_attempts"] == 192
    assert report["termination"] == "objective_point_budget_exhausted"
    assert report["counters"]["major_iteration_observations"] == 1
    assert report["counters"]["incumbent_updates"] == 1
    assert final.tolist() == [[1., 0., 0.]]
    assert report["final"]["total_energy_kcal_mol"] == 1.
    assert len([r for r in rows if r["event"] == "objective_point"]) == 192


@pytest.mark.parametrize("failure", [FloatingPointError, ValueError])
def test_failed_trial_is_counted_and_fatal_without_fake_objective_or_new_incumbent(monkeypatch, failure):
    seen, rows = [], []
    def tracked(xyz):
        seen.append(xyz.clone())
        if float(xyz[0, 0]) == 2.:
            raise failure("native trial failure")
        return unconstrained_objective(xyz)
    def optimizer(fun, x0, **kwargs):
        kwargs["callback"](np.array([1., 0., 0.]))
        fun(np.array([2., 0., 0.]))
        pytest.fail("fatal failure substituted an objective")
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), tracked, valid, rows.append)
    assert len(seen) == report["counters"]["objective_point_attempts"] == 3
    assert report["counters"]["failed_objective_point_attempts"] == 1
    assert report["termination"] == "fatal_numerical_applicability_or_optimizer_failure"
    assert final.tolist() == [[1., 0., 0.]]
    assert [r for r in rows if r["event"] == "objective_point"][-1]["outcome"] == "fatal_evaluation_failure"


@pytest.mark.parametrize("invalid", ["strain", "full_validity", "energy", "incomplete"])
def test_invalid_callback_and_successful_terminal_cannot_replace_feasible_incumbent(monkeypatch, invalid):
    def callback_objective(xyz):
        value = unconstrained_objective(xyz)
        if invalid == "strain" and float(xyz[0, 0]) == 2.:
            return value[0], value[1], 5. + 1e-12, torch.zeros_like(xyz), value[4]
        if invalid == "energy" and float(xyz[0, 0]) == 2.:
            return 4. + 1e-12, value[1], value[2], value[3], value[4]
        return value
    def validation(xyz):
        bad = float(xyz[0, 0]) == 2.
        return {"complete": not (bad and invalid == "incomplete"), "valid": not (bad and invalid == "full_validity")}
    def optimizer(fun, x0, **kwargs):
        kwargs["callback"](np.array([1., 0., 0.]))
        kwargs["callback"](np.array([2., 0., 0.]))
        return returned([2., 0., 0.], success=True)
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, first = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), callback_objective, validation, lambda _: None)
    assert final.tolist() == first.tolist() == [[1., 0., 0.]]
    assert report["scipy_result"]["success"]
    assert report["counters"]["major_iteration_observations"] == 2
    assert report["counters"]["incumbent_updates"] == 1
    assert not report["major_and_terminal_observations"][-1]["admission"]["eligible"]


def test_terminal_point_requires_charged_evaluation_and_independent_admission(monkeypatch):
    def optimizer(fun, x0, **kwargs):
        kwargs["callback"](np.array([.5, 0., 0.]))
        return returned([1., 0., 0.], success=False)
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), unconstrained_objective, valid, lambda _: None)
    assert final.tolist() == [[1., 0., 0.]]
    assert report["retained_incumbent_origin"] == "terminal_state_observation"
    assert report["counters"]["objective_point_attempts"] == 3
    assert not report["scipy_result"]["success"]


def test_cache_hit_revalidates_source_and_cannot_hide_integrity_change(monkeypatch):
    flag = [True]
    def intact():
        if not flag[0]:
            raise ValueError("source changed")
    def optimizer(fun, x0, **kwargs):
        kwargs["callback"](np.array([1., 0., 0.]))
        fun(np.array([1., 0., 0.]))
        flag[0] = False
        fun(np.array([1., 0., 0.]))
        pytest.fail("cache concealed changed source")
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), unconstrained_objective, valid, lambda _: None, intact=intact)
    assert final.tolist() == [[1., 0., 0.]]
    assert report["termination"] == "source_integrity_failure"
    assert report["status"] == "INVALID_SOURCE_INTEGRITY"
    assert not report["constrained_stationary"] and not report["kkt"]["stationary"]
    assert report["counters"]["objective_point_attempts"] == 2


def test_exact_coordinate_cache_is_not_rounded_and_original_input_is_preserved():
    original = torch.zeros(1, 3, dtype=torch.float64)
    seen = []
    def tracked(xyz):
        seen.append(xyz.clone())
        return unconstrained_objective(xyz)
    cache = core.PointCache(original, (), tracked, lambda _: None, lambda: None, core.PROTOCOL)
    cache.get(np.zeros(3), "initial")
    cache.get(np.zeros(3), "duplicate")
    cache.get(np.array([np.nextafter(0., 1.), 0., 0.]), "distinct_subnormal")
    assert len(seen) == 2 and cache.counts["cache_hits"] == 1
    assert torch.equal(original, torch.zeros_like(original))


@pytest.mark.parametrize("field", ["ftol", "objective_divisor", "internal_increase_limit_kcal_mol",
    "original_bond_length_change_limit_angstrom", "active_normalized_constraint_maximum",
    "kkt_maximum_atom_residual_kcal_mol_angstrom", "complementarity_tolerance_kcal_mol",
    "raw_maximum_atom_force_tolerance_kcal_mol_angstrom"])
@pytest.mark.parametrize("value", [0., -1., float("inf"), float("nan")])
def test_invalid_numerical_protocol_stops_before_any_objective(field, value):
    def forbidden(_):
        pytest.fail("invalid protocol reached physics")
    with pytest.raises(ValueError, match="finite_positive"):
        core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), forbidden, valid, lambda _: None,
                           protocol={**core.PROTOCOL, field: value})


def test_ineligible_initial_state_never_enters_optimizer(monkeypatch):
    monkeypatch.setattr(core, "minimize", lambda *args, **kwargs: pytest.fail("invalid initial reached solver"))
    with pytest.raises(ValueError, match="initial_full_feasibility"):
        core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), objective,
                           lambda _: {"complete": True, "valid": False}, lambda _: None)


def test_original_bond_changes_use_both_exact_sides_without_coordinate_box():
    xyz = np.array([[0., 0., 0.], [1., 0., 0.]])
    for delta in (-.150001, .150001):
        moved = xyz.copy()
        moved[1, 0] += delta
        values, _, changes = core.normalized_constraints(moved, 0., np.zeros_like(xyz), 0., ((0, 1),), (1.,), core.PROTOCOL)
        assert (values < 0).sum() == 1
        assert abs(changes[0]) > .15


def test_full_validity_on_every_completed_trial_is_cached_without_modifying_invalid_trial_objective(monkeypatch):
    validity_points, rows = [], []
    def validation(xyz):
        value = float(xyz[0, 0])
        validity_points.append(value)
        return {"complete": True, "valid": value != .75}
    def optimizer(fun, x0, **kwargs):
        assert "bounds" not in kwargs
        assert fun(np.array([.75, 0., 0.])) == pytest.approx((.75 - 2.)**2 / 1000.)
        assert fun(np.array([.75, 0., 0.])) == pytest.approx((.75 - 2.)**2 / 1000.)
        kwargs["callback"](np.array([.25, 0., 0.]))
        return returned([.75, 0., 0.])
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), unconstrained_objective, validation, rows.append)
    assert final.tolist() == [[.25, 0., 0.]]
    assert validity_points == [0., .75, .25]
    assert report["counters"]["validity_calls"] == report["counters"]["objective_point_attempts"] == 3
    assert report["counters"]["validity_wall_seconds"] >= 0.
    trials = [r for r in rows if r["event"] == "objective_point"]
    assert all("full_validity" in r for r in trials)
    assert trials[1]["outcome"] == "evaluated" and not trials[1]["full_validity"]["valid"]


def test_only_optimizer_objective_and_gradient_are_scaled_not_constraints_or_kkt(monkeypatch):
    def optimizer(fun, x0, **kwargs):
        assert fun(x0) == .004
        np.testing.assert_allclose(kwargs["jac"](x0), [-.004, 0., 0.], atol=0, rtol=0)
        np.testing.assert_allclose(kwargs["constraints"]["fun"](x0), [1.], atol=0, rtol=0)
        np.testing.assert_allclose(kwargs["constraints"]["jac"](np.array([1., 0., 0.])), [[-2., 0., 0.]], atol=0, rtol=0)
        return returned([1., 0., 0.])
    monkeypatch.setattr(core, "minimize", optimizer)
    _, report, _ = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), objective, valid, lambda _: None)
    assert report["final"]["total_energy_kcal_mol"] == 1.
    assert report["final"]["total_gradient_kcal_mol_angstrom"] == [[-2., 0., 0.]]
    assert report["kkt"]["multipliers_kcal_mol"] == [1.]


def test_bond_violation_rejected_independently_of_passing_full_validity(monkeypatch):
    original = torch.tensor([[0., 0., 0.], [1., 0., 0.]], dtype=torch.float64)
    def energy(xyz):
        gradient = torch.zeros_like(xyz)
        gradient[1, 0] = -1.
        return -float(xyz[1, 0]), gradient, 0., torch.zeros_like(xyz), {}
    within = np.array([[0., 0., 0.], [1.149, 0., 0.]])
    beyond = np.array([[0., 0., 0.], [1.1500000001, 0., 0.]])
    def optimizer(fun, x0, **kwargs):
        kwargs["callback"](within.reshape(-1))
        kwargs["callback"](beyond.reshape(-1))
        return returned(beyond)
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(original, ((0, 1),), energy, valid, lambda _: None)
    np.testing.assert_array_equal(final.numpy(), within)
    terminal = report["major_and_terminal_observations"][-1]["admission"]
    assert terminal["validity"]["valid"]
    assert not terminal["checks"]["original_bonds_within_exact_limit"]


def test_source_change_during_failed_evaluation_overrides_retryable_numerical_error(monkeypatch):
    flag = [True]
    def intact():
        if not flag[0]:
            raise ValueError("changed source during failure")
    def energy(xyz):
        if float(xyz[0, 0]) == 1.:
            flag[0] = False
            raise FloatingPointError("native error")
        return unconstrained_objective(xyz)
    def optimizer(fun, x0, **kwargs):
        fun(np.array([1., 0., 0.]))
        pytest.fail("source failure was ignored")
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, first = core.bounded_slsqp(torch.zeros(1, 3, dtype=torch.float64), (), energy, valid, lambda _: None, intact=intact)
    assert final.tolist() == [[0., 0., 0.]] and first is None
    assert report["status"] == "INVALID_SOURCE_INTEGRITY"
    assert not report["kkt"]["stationary"] and not report["original_force_and_research_admission_gates_passed"]
    assert report["counters"]["objective_point_attempts"] == 2
    assert report["counters"]["failed_objective_point_attempts"] == 1


def test_original_input_mutation_is_detected_even_without_external_integrity_hook(monkeypatch):
    original = torch.zeros(1, 3, dtype=torch.float64)
    def optimizer(fun, x0, **kwargs):
        original[0, 0] = .1
        fun(x0)
        pytest.fail("original mutation was not detected")
    monkeypatch.setattr(core, "minimize", optimizer)
    final, report, _ = core.bounded_slsqp(original, (), unconstrained_objective, valid, lambda _: None)
    assert final.tolist() == [[0., 0., 0.]]
    assert report["status"] == "INVALID_SOURCE_INTEGRITY"
