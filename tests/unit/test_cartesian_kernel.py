"""Independent algebra and accounting checks; no molecular evaluator is used.

The dense inverse-BFGS oracle below uses matrix rank-two updates, never the
production two-loop routine.  Its secant pairs come from accepted coordinates
and an analytic Hessian, not from the machine's stored history.
"""

from copy import deepcopy
import math

import pytest
import torch

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from betelgeuze_product.cpu_refinement_v1_3 import kernel
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_v1_3.kernel import (
    CartesianMachine,
    make_observation,
)


def _tensor(values):
    return torch.tensor(values, dtype=torch.float64).reshape(1, -1, 3)


def _decode(values):
    assert all(type(value) is str for row in values for value in row)
    return _tensor([[float.fromhex(value) for value in row] for row in values])


def _config(**updates):
    return SolverConfig(**{
        "max_objective_attempts": 30,
        "max_accepted_steps": 12,
        "force_tolerance": 1.e-12,
        **updates,
    })


def _components(energy):
    return {"total": energy, "ligand_internal": energy,
            "cross_lennard_jones": 0., "cross_screened_coulomb": 0.}


def _quadratic(matrix):
    def objective(coordinates):
        x = coordinates.flatten()
        gradient = matrix @ x
        return float(.5 * torch.dot(x, gradient)), -gradient.reshape_as(coordinates)
    return objective


def _observe(intent, objective):
    coordinates = _decode(intent["coordinates"])
    energy, forces = objective(coordinates)
    return make_observation(intent["attempt"], coordinates, energy, forces,
                            _components(energy))


def _drive(machine, objective):
    rows = []
    for _ in range(100):
        intent = machine.next_intent()
        if intent is None:
            return rows
        observation = _observe(intent, objective)
        decision = machine.commit(intent, observation)
        rows.append((intent, observation, decision))
    pytest.fail("bounded synthetic machine failed to stop")


def _linear(coordinates):
    return float(coordinates.sum()), -torch.ones_like(coordinates)


def _dense_inverse(hessian, transitions, size, initial_scale):
    """BFGS rank-two updates from analytic secants, newest retained pair H0."""
    identity = torch.eye(hessian.shape[0], dtype=torch.float64)
    pairs = [(after - before, hessian @ (after - before))
             for before, after in transitions[-size:]]
    if not pairs:
        return initial_scale * identity
    s, y = pairs[-1]
    inverse = (torch.dot(s, y) / torch.dot(y, y)) * identity
    for s, y in pairs:
        rho = 1. / torch.dot(s, y)
        left = identity - rho * torch.outer(s, y)
        inverse = left @ inverse @ left.T + rho * torch.outer(s, s)
    return inverse


@pytest.mark.parametrize("history_size", [1, 2, 4])
def test_lbfgs_directions_match_independent_dense_bfgs_after_fifo(history_size):
    matrix = torch.tensor([[9., 2., 1.], [2., 4., .5], [1., .5, 2.]],
                          dtype=torch.float64)
    config = _config(initial_step_size=.2, maximum_atom_displacement=1.,
                     history_size=history_size, max_accepted_steps=7)
    machine = CartesianMachine(_tensor([.4, -.2, .6]), config)
    objective = _quadratic(matrix)
    transitions = []
    accepted_point = None
    directions_checked = 0
    for _ in range(config.max_objective_attempts):
        intent = machine.next_intent()
        if intent is None:
            break
        point = _decode(intent["coordinates"]).flatten()
        if accepted_point is not None:
            inverse = _dense_inverse(matrix, transitions, history_size,
                                     config.initial_step_size)
            direction = -(inverse @ (matrix @ accepted_point))
            direction *= min(1., config.maximum_atom_displacement /
                             max(float(torch.linalg.vector_norm(direction)), 1.e-300))
            torch.testing.assert_close(_decode(intent["direction"]).flatten(),
                                       direction, rtol=2.e-12, atol=2.e-14)
            expected_point = accepted_point + float.fromhex(intent["step"]) * direction
            torch.testing.assert_close(point, expected_point, rtol=2.e-12, atol=2.e-14)
            directions_checked += 1
        decision = machine.commit(intent, _observe(intent, objective))
        if decision["outcome"] in {"initial", "accepted"}:
            if accepted_point is not None:
                transitions.append((accepted_point.clone(), point.clone()))
                assert decision["curvature"] == "retained"
            accepted_point = point
    assert machine.next_intent() is None
    assert len(transitions) == 7
    assert directions_checked >= 7
    assert len(transitions) > history_size  # Exercise forgetting, not only H0.


# Generated once from the frozen external research optimizer (pure quadratic):
# SHA256 aee559672ed8861d1a3376e644bc0a6e9049cc3d09172df218c13226194d8aee.
# These constants keep this test portable; the external run packet is not needed.
_FROZEN_FINAL = {
    "sd": ["-0x1.495af294dd72ap-2", "-0x1.eff3ade225faep-4", "0x1.668c26138ffd0p-7"],
    "lbfgs": ["-0x1.a47ae5b71cc27p-7", "-0x1.dbb4081dc2690p-8", "-0x1.07e89f966e96cp-7"],
}
_FROZEN_ENERGIES = {
    "sd": ["0x1.2e147ae147ae1p+0", "0x1.b27bb2fec56d9p-1", "0x1.72352eb5f5f11p-1",
           "0x1.4f1b07c342e0dp-1", "0x1.36c4972bfda0cp-1", "0x1.2328fb0c7436cp-1"],
    "lbfgs": ["0x1.2e147ae147ae1p+0", "0x1.b27bb2fec56d9p-1", "0x1.27bbf846eac76p-3",
              "0x1.4f98eb7f907b7p-4", "0x1.80143a623f125p-9", "0x1.42753e882980bp-10"],
}


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_matches_frozen_external_quadratic_trace(algorithm):
    matrix = torch.tensor([[9., 2., 1.], [2., 4., .5], [1., .5, 2.]],
                          dtype=torch.float64)
    config = _config(algorithm=algorithm, initial_step_size=.2,
                     maximum_atom_displacement=1., history_size=2,
                     max_objective_attempts=9, max_accepted_steps=5,
                     max_backtracks=4)
    rows = _drive(CartesianMachine(_tensor([.4, -.2, .6]), config), _quadratic(matrix))
    assert [row[2]["outcome"] for row in rows] == ["initial"] + ["accepted"] * 5
    assert [row[0]["trial"] for row in rows] == [0] * 6
    observed_energies = [float.fromhex(row[1]["energy"]) for row in rows]
    assert observed_energies == pytest.approx(
        [float.fromhex(value) for value in _FROZEN_ENERGIES[algorithm]], rel=2.e-13, abs=2.e-15)
    torch.testing.assert_close(_decode(rows[-1][0]["coordinates"]),
                               _decode([_FROZEN_FINAL[algorithm]]),
                               rtol=2.e-12, atol=2.e-14)


def test_observation_retains_full_vectors_and_maximum_atom_norm():
    coordinates = _tensor([[1., 2., 3.], [-1., 0., 4.]])
    forces = _tensor([[3., 4., 0.], [0., 0., 2.]])
    value = make_observation(1, coordinates, 7., forces, _components(7.))
    assert value["maximum_raw_atom_force"] == 5..hex()
    assert value["attempt"] == 1
    assert value["energy"] == 7..hex()
    torch.testing.assert_close(_decode(value["forces"]), forces, rtol=0, atol=0)
    torch.testing.assert_close(_decode(value["coordinates"]), coordinates, rtol=0, atol=0)
    assert value["components"] == {key: item.hex() for key, item in _components(7.).items()}


@pytest.mark.parametrize("maximum,converges", [(1.e-3, True),
    (math.nextafter(1.e-3, math.inf), False)])
def test_raw_force_threshold_inclusive_without_rounding(maximum, converges):
    machine = CartesianMachine(_tensor([[0., 0., 0.], [0., 0., 0.]]),
                               _config(force_tolerance=1.e-3))
    intent = machine.next_intent()
    forces = _tensor([[maximum, 0., 0.], [0., maximum / 2., 0.]])
    machine.commit(intent, make_observation(1, _decode(intent["coordinates"]),
                                           0., forces, _components(0.)))
    assert (machine.next_intent() is None) == converges


def test_force_threshold_is_per_atom_norm_not_max_component():
    machine = CartesianMachine(_tensor([0., 0., 0.]), _config(force_tolerance=1.))
    intent = machine.next_intent()
    machine.commit(intent, make_observation(1, _decode(intent["coordinates"]),
                                           0., _tensor([.8, .8, 0.]), _components(0.)))
    assert machine.next_intent() is not None  # Every component < 1, norm > 1.


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_displacement_cap_uses_maximum_atom_length(algorithm):
    config = _config(algorithm=algorithm, initial_step_size=.1,
                     maximum_atom_displacement=.2, max_accepted_steps=1)
    machine = CartesianMachine(_tensor([[0., 0., 0.], [0., 0., 0.]]), config)
    forces = _tensor([[3., 4., 0.], [0., 0., 2.]])
    def objective(point):
        return -float((point * forces).sum()), forces.clone()
    rows = _drive(machine, objective)
    assert len(rows) == 2
    torch.testing.assert_close(_decode(rows[1][0]["coordinates"]),
                               _tensor([[.12, .16, 0.], [0., 0., .08]]),
                               rtol=1.e-15, atol=1.e-16)


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_armijo_rejections_count_and_backtrack_from_same_accepted_point(algorithm):
    config = _config(algorithm=algorithm, initial_step_size=10.,
                     maximum_atom_displacement=100., max_accepted_steps=1,
                     max_objective_attempts=5, max_backtracks=3)
    rows = _drive(CartesianMachine(_tensor([1., 0., 0.]), config),
                  _quadratic(torch.eye(3, dtype=torch.float64)))
    assert [row[2]["outcome"] for row in rows] == [
        "initial", "rejected_armijo", "rejected_armijo", "rejected_armijo", "accepted"]
    assert [row[0]["attempt"] for row in rows] == [1, 2, 3, 4, 5]
    assert [row[0]["iteration"] for row in rows] == [0, 1, 1, 1, 1]
    assert [row[0]["trial"] for row in rows] == [0, 0, 1, 2, 3]
    assert [_decode(row[0]["coordinates"])[0, 0, 0].item() for row in rows] == [
        1., -9., -4., -1.5, -.25]
    assert [row[2]["curvature"] for row in rows[:-1]] == ["none"] * 4


def test_failed_evaluation_consumes_attempt_and_backtracks_without_history():
    machine = CartesianMachine(_tensor([1., 0., 0.]),
                               _config(initial_step_size=1., maximum_atom_displacement=10.,
                                       max_objective_attempts=3, max_accepted_steps=1))
    initial = machine.next_intent()
    machine.commit(initial, _observe(initial, _linear))
    failed = machine.next_intent()
    decision = machine.commit(failed, None, failure="retryable")
    assert decision["outcome"] == "rejected_evaluation"
    assert decision["curvature"] == "none"
    retry = machine.next_intent()
    assert retry["attempt"] == 3
    assert retry["trial"] == 1
    assert retry["iteration"] == failed["iteration"] == 1
    assert retry["direction"] == failed["direction"]
    assert float.fromhex(retry["step"]) == float.fromhex(failed["step"]) / 2.
    assert machine.commit(retry, _observe(retry, _linear))["outcome"] == "accepted"
    assert machine.next_intent() is None
    state = machine.snapshot()
    assert (state["attempts"], state["accepted"], state["failed_evaluations"]) == (3, 1, 1)
    assert state["history"] == []
    assert state["skipped_curvature"] == 1


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_initial_and_rejected_trials_share_hard_objective_budget(limit):
    machine = CartesianMachine(_tensor([1., 0., 0.]),
                               _config(initial_step_size=10., maximum_atom_displacement=100.,
                                       max_objective_attempts=limit, max_backtracks=12))
    rows = _drive(machine, _quadratic(torch.eye(3, dtype=torch.float64)))
    assert len(rows) == limit
    assert [row[2]["outcome"] for row in rows] == ["initial"] + ["rejected_armijo"] * (limit - 1)
    assert machine.next_intent() is None
    state = machine.snapshot()
    assert state["status"] == "objective_budget_exhausted"
    assert (state["attempts"], state["accepted"], state["failed_evaluations"]) == (limit, 0, 0)
    assert state["current"] == state["initial"] == rows[0][1]


def test_zero_accepted_budget_still_records_initial_observation():
    rows = _drive(CartesianMachine(_tensor([1., 0., 0.]),
                                   _config(max_accepted_steps=0)), _linear)
    assert len(rows) == 1
    assert rows[0][2]["outcome"] == "initial"


@pytest.mark.parametrize("objective", [_linear,
    lambda point: (-float(.5 * point.square().sum()), point.clone())])
def test_zero_or_negative_curvature_is_skipped_and_not_reused(objective):
    config = _config(initial_step_size=.1, maximum_atom_displacement=10.,
                     max_accepted_steps=2)
    rows = _drive(CartesianMachine(_tensor([1., 0., 0.]), config), objective)
    assert [row[2]["outcome"] for row in rows] == ["initial", "accepted", "accepted"]
    assert [row[2]["curvature"] for row in rows[1:]] == ["skipped", "skipped"]
    force_after_first = _decode(rows[1][1]["forces"])
    torch.testing.assert_close(_decode(rows[2][0]["direction"]),
                               config.initial_step_size * force_after_first,
                               rtol=0, atol=0)


def test_next_intent_is_idempotent_and_returns_detached_public_data():
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config())
    first = machine.next_intent()
    state = deepcopy(machine.snapshot())
    assert machine.next_intent() == first
    assert machine.snapshot() == state
    first["coordinates"][0][0] = 99..hex()
    assert machine.next_intent()["coordinates"][0][0] == 1..hex()
    intent = machine.next_intent()
    machine.commit(intent, _observe(intent, _linear))
    pending = machine.next_intent()
    assert machine.next_intent() == pending


@pytest.mark.parametrize("field,value", [("attempt", 2), ("iteration", 1),
    ("trial", 1), ("step", 1..hex()), ("restarted", True),
    ("coordinates", [[2..hex(), 0..hex(), 0..hex()]]),
    ("direction", [[1..hex(), 0..hex(), 0..hex()]])])
def test_rejects_substituted_intent_before_state_mutation(field, value):
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config())
    intent = machine.next_intent()
    observation = _observe(intent, _linear)
    before = deepcopy(machine.snapshot())
    substituted = deepcopy(intent)
    substituted[field] = value
    with pytest.raises(ResearchError):
        machine.commit(substituted, observation)
    assert machine.snapshot() == before
    assert machine.next_intent() == intent


@pytest.mark.parametrize("change", ["attempt", "coordinates", "norm", "energy", "extra"])
def test_rejects_observation_mismatch_before_state_mutation(change):
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config())
    intent = machine.next_intent()
    observation = _observe(intent, _linear)
    before = deepcopy(machine.snapshot())
    if change == "attempt":
        observation["attempt"] += 1
    elif change == "coordinates":
        observation["coordinates"][0][0] = 2..hex()
    elif change == "norm":
        observation["maximum_raw_atom_force"] = 0..hex()
    elif change == "energy":
        observation["energy"] = 8..hex()  # Components still bind the original total.
    else:
        observation["unbound"] = True
    with pytest.raises(ResearchError):
        machine.commit(intent, observation)
    assert machine.snapshot() == before
    assert machine.next_intent() == intent


def test_commit_of_already_committed_intent_is_rejected():
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config())
    intent = machine.next_intent()
    observation = _observe(intent, _linear)
    machine.commit(intent, observation)
    before = deepcopy(machine.snapshot())
    with pytest.raises(ResearchError):
        machine.commit(intent, observation)
    assert machine.snapshot() == before


@pytest.mark.parametrize("failure", ["retryable", "fatal"])
def test_failed_initial_observation_terminates_with_known_failed_attempt(failure):
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config())
    decision = machine.commit(machine.next_intent(), None, failure=failure)
    assert decision == {"outcome": "rejected_evaluation", "curvature": "none",
                        "status": "evaluation_failed"}
    assert machine.next_intent() is None
    state = machine.snapshot()
    assert (state["attempts"], state["accepted"], state["failed_evaluations"]) == (1, 0, 1)
    assert state["initial"] is state["current"] is None


@pytest.mark.parametrize("failure,expected_status", [
    ("retryable", "line_search_failed"), ("fatal", "evaluation_failed")])
def test_failed_terminal_trial_preserves_last_accepted_observation(failure, expected_status):
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config(max_backtracks=0))
    initial = machine.next_intent()
    observation = _observe(initial, _linear)
    machine.commit(initial, observation)
    decision = machine.commit(machine.next_intent(), None, failure=failure)
    assert decision["status"] == expected_status
    assert machine.next_intent() is None
    state = machine.snapshot()
    assert (state["attempts"], state["accepted"], state["failed_evaluations"]) == (2, 0, 1)
    assert state["current"] == observation
    assert state["history"] == []


def test_convergence_precedes_exhausted_budget_and_step_limit():
    machine = CartesianMachine(_tensor([0., 0., 0.]),
                               _config(max_objective_attempts=1, max_accepted_steps=0))
    rows = _drive(machine, _quadratic(torch.eye(3, dtype=torch.float64)))
    assert len(rows) == 1
    assert rows[0][2]["status"] == "force_converged"
    assert machine.snapshot()["attempts"] == 1


def test_history_binds_accepted_transitions_and_excludes_rejected_trial():
    matrix = torch.diag(torch.tensor([1., 2., 3.], dtype=torch.float64))
    config = _config(initial_step_size=10., maximum_atom_displacement=100.,
                     history_size=2, max_accepted_steps=3, max_objective_attempts=25)
    machine = CartesianMachine(_tensor([1., .4, -.2]), config)
    rows = _drive(machine, _quadratic(matrix))
    accepted = [row for row in rows if row[2]["outcome"] in {"initial", "accepted"}]
    rejected = {row[0]["attempt"] for row in rows if row[2]["outcome"].startswith("rejected")}
    assert rejected
    assert len(accepted) == 4
    history = machine.snapshot()["history"]
    assert len(history) == config.history_size
    for pair, before, after in zip(history, accepted[-3:-1], accepted[-2:]):
        assert set(pair) == {"source_attempt", "target_attempt", "s", "y"}
        assert pair["source_attempt"] == before[0]["attempt"]
        assert pair["target_attempt"] == after[0]["attempt"]
        assert pair["source_attempt"] not in rejected
        assert pair["target_attempt"] not in rejected
        displacement = _decode(after[0]["coordinates"]) - _decode(before[0]["coordinates"])
        torch.testing.assert_close(_decode(pair["s"]), displacement, rtol=0, atol=0)
        expected_y = (matrix @ displacement.flatten()).reshape_as(displacement)
        torch.testing.assert_close(_decode(pair["y"]), expected_y, rtol=1.e-14, atol=1.e-15)


@pytest.mark.parametrize("defect", ["non_descent", "nonfinite", "division"])
def test_direction_fault_restarts_once_and_keeps_retry_direction(monkeypatch, defect):
    machine = CartesianMachine(_tensor([1., .4, -.2]),
                               _config(initial_step_size=.1, maximum_atom_displacement=10.))
    objective = _quadratic(torch.eye(3, dtype=torch.float64))
    for _ in range(2):
        intent = machine.next_intent()
        machine.commit(intent, _observe(intent, objective))
    before = machine.snapshot()
    assert len(before["history"]) == 1

    def broken_inverse(gradient, *_):
        if defect == "division":
            raise ZeroDivisionError("synthetic inverse failure")
        if defect == "nonfinite":
            return torch.full_like(gradient, math.inf)
        return -gradient  # Its negative points uphill, irrespective of Hessian.

    monkeypatch.setattr(kernel, "_two_loop", broken_inverse)
    intent = machine.next_intent()
    assert intent["restarted"] is not None
    assert machine.next_intent() == intent
    assert machine.snapshot() == before  # Merely asking for a trial does no work.
    torch.testing.assert_close(_decode(intent["direction"]),
                               .1 * _decode(before["current"]["forces"]), rtol=0, atol=0)
    machine.commit(intent, None, failure="retryable")
    after_failure = machine.snapshot()
    assert after_failure["restarts"] == 1
    assert after_failure["history"] == []
    retry = machine.next_intent()
    assert retry["direction"] == intent["direction"]
    assert retry["restarted"] == intent["restarted"]
    assert retry["trial"] == 1
    machine.commit(retry, _observe(retry, objective))
    final = machine.snapshot()
    assert final["restarts"] == 1
    assert final["accepted"] == 2
    assert final["failed_evaluations"] == 1
    assert len(final["history"]) == 1


@pytest.mark.parametrize("coordinates", [
    torch.zeros((1, 1, 3), dtype=torch.float32),
    torch.zeros((1, 0, 3), dtype=torch.float64),
    torch.zeros((2, 1, 3), dtype=torch.float64),
    torch.zeros((1, 3), dtype=torch.float64),
    torch.zeros((1, 257, 3), dtype=torch.float64),
    _tensor([math.nan, 0., 0.]),
    _tensor([math.inf, 0., 0.]),
])
def test_constructor_rejects_unsupported_coordinate_arrays(coordinates):
    with pytest.raises(ResearchError):
        CartesianMachine(coordinates, _config())


@pytest.mark.parametrize("defect", ["force_shape", "force_dtype", "nonfinite_force",
    "overflow_norm", "nonfinite_energy", "missing_component", "inconsistent_total"])
def test_observation_rejects_malformed_or_nonfinite_full_data(defect):
    coordinates, forces, energy = _tensor([1., 0., 0.]), _tensor([-1., 0., 0.]), 1.
    components = _components(energy)
    if defect == "force_shape":
        forces = _tensor([[1., 0., 0.], [0., 0., 0.]])
    elif defect == "force_dtype":
        forces = forces.float()
    elif defect == "nonfinite_force":
        forces[0, 0, 0] = math.nan
    elif defect == "overflow_norm":
        forces[:] = 1.e308  # Finite components with an unrepresentable norm.
    elif defect == "nonfinite_energy":
        energy = math.inf
    elif defect == "missing_component":
        del components["cross_lennard_jones"]
    else:
        components["total"] = 9.
    with pytest.raises(ResearchError):
        make_observation(1, coordinates, energy, forces, components)


@pytest.mark.parametrize("failure,with_observation", [
    (None, False), ("retryable", True), ("fatal", True), ("other", False)])
def test_commit_requires_exactly_one_observation_or_known_failure(failure, with_observation):
    machine = CartesianMachine(_tensor([1., 0., 0.]), _config())
    intent = machine.next_intent()
    before = machine.snapshot()
    with pytest.raises(ResearchError):
        machine.commit(intent, _observe(intent, _linear) if with_observation else None,
                       failure=failure)
    assert machine.snapshot() == before


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
def test_binary64_rounding_displacement_and_no_movement_are_counted(algorithm):
    # At 2**48, adjacent coordinates are 0.0625 apart. The nominal 0.05 step
    # rounds above the cap; its half step rounds to the accepted point itself.
    machine = CartesianMachine(_tensor([float(2**48), 0., 0.]),
                               _config(algorithm=algorithm, initial_step_size=.05,
                                       maximum_atom_displacement=.05, max_backtracks=1))

    def affine_objective(point):
        return -float(point[0, 0, 0]), _tensor([1., 0., 0.])

    rows = _drive(machine, affine_objective)
    assert [row[2]["outcome"] for row in rows] == [
        "initial", "rejected_displacement", "rejected_non_descent"]
    state = machine.snapshot()
    assert state["status"] == "line_search_failed"
    assert (state["attempts"], state["accepted"], state["failed_evaluations"]) == (3, 0, 0)
    assert state["current"] == state["initial"] == rows[0][1]
    assert state["history"] == []
