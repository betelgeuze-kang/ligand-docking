"""Pure arithmetic/state-machine oracles; no molecular evaluator is called."""

import math
import random
import pytest
import torch
from betelgeuze_product.cpu_refinement_v1_3.kernel import (
    _two_loop,
    CartesianMachine,
    make_observation,
)
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def mv(a, b):
    return [dot(row, b) for row in a]


def mm(a, b):
    return [
        [math.fsum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
        for i in range(len(a))
    ]


def dense_inverse_bfgs(g, history, initial_scale):
    n = len(g)
    scale = (
        initial_scale
        if not history
        else dot(*history[-1]) / dot(history[-1][1], history[-1][1])
    )
    h = [[scale * float(i == j) for j in range(n)] for i in range(n)]
    for s, y in history:
        rho = 1 / dot(s, y)
        left = [[float(i == j) - rho * s[i] * y[j] for j in range(n)] for i in range(n)]
        right = [
            [float(i == j) - rho * y[i] * s[j] for j in range(n)] for i in range(n)
        ]
        product = mm(mm(left, h), right)
        h = [[product[i][j] + rho * s[i] * s[j] for j in range(n)] for i in range(n)]
    return mv(h, g)


@pytest.mark.parametrize("seed", range(20))
def test_two_loop_matches_independent_dense_matrix(seed):
    rng = random.Random(seed)
    g = [rng.uniform(-2, 2) for _ in range(6)]
    history = []
    for _ in range(seed % 6):
        s = [rng.uniform(-1, 1) for _ in range(6)]
        y = [(i + 1) * v for i, v in enumerate(s)]
        history.append((s, y))
    expected = dense_inverse_bfgs(g, history, 0.001)
    actual = _two_loop(
        torch.tensor(g, dtype=torch.float64),
        [
            (torch.tensor(s, dtype=torch.float64), torch.tensor(y, dtype=torch.float64))
            for s, y in history
        ],
        0.001,
    )
    assert actual.tolist() == pytest.approx(expected, rel=1e-12, abs=1e-12)


def config(algorithm, **kw):
    return SolverConfig(
        algorithm=algorithm,
        max_objective_attempts=kw.pop("max_objective_attempts", 17),
        max_accepted_steps=4,
        max_backtracks=3,
        max_restart_verifications=0,
        **kw,
    )


def decode(rows):
    return torch.tensor(
        [[[float.fromhex(v) for v in row] for row in rows]], dtype=torch.float64
    )


def obs(i, xyz, force, energy):
    return make_observation(
        i,
        xyz,
        energy,
        force,
        {
            "ligand_internal": energy,
            "cross_lennard_jones": 0.0,
            "cross_screened_coulomb": 0.0,
            "total": energy,
        },
    )


@pytest.mark.parametrize("algorithm", ["sd", "lbfgs"])
@pytest.mark.parametrize("force_scale", [1.0, 1000.0])
def test_initial_step_and_atom_cap(algorithm, force_scale):
    xyz = torch.tensor([[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]], dtype=torch.float64)
    f = (
        torch.tensor([[[1.0, 2.0, 3.0], [-4.0, 5.0, 6.0]]], dtype=torch.float64)
        * force_scale
    )
    c = config(algorithm)
    machine = CartesianMachine(xyz, c)
    first = machine.next_intent()
    assert torch.equal(decode(first["coordinates"]), xyz)
    machine.commit(first, obs(1, xyz, f, 100.0))
    nxt = machine.next_intent()
    maximum = max(math.sqrt(sum(v * v for v in row)) for row in f[0].tolist())
    scale = min(1.0, 0.05 / (0.001 * maximum))
    expected = xyz + 0.001 * f * scale
    torch.testing.assert_close(
        decode(nxt["coordinates"]), expected, rtol=0.0, atol=2e-15
    )
    assert (
        max(
            math.sqrt(sum(v * v for v in row))
            for row in (decode(nxt["coordinates"]) - xyz)[0].tolist()
        )
        <= 0.05 + 1e-12
    )


def test_sd_rejected_trial_consumes_budget():
    xyz = torch.tensor([[[1.0, 2.0, 3.0]]], dtype=torch.float64)
    f = torch.tensor([[[1.0, 0.0, 0.0]]], dtype=torch.float64)
    m = CartesianMachine(xyz, config("sd", max_objective_attempts=2))
    i = m.next_intent()
    m.commit(i, obs(1, xyz, f, 100.0))
    i = m.next_intent()
    out = m.commit(i, obs(2, decode(i["coordinates"]), f, 100.0))
    state = m.snapshot()
    assert (
        out["outcome"] == "rejected_armijo"
        and state["attempts"] == 2
        and state["accepted"] == 0
        and state["status"] == "objective_budget_exhausted"
    )
    assert state["current"]["coordinates"] == state["original_coordinates"]


def test_retryable_failure_is_not_free():
    xyz = torch.tensor([[[1.0, 2.0, 3.0]]], dtype=torch.float64)
    f = torch.tensor([[[1.0, 0.0, 0.0]]], dtype=torch.float64)
    m = CartesianMachine(xyz, config("sd", max_objective_attempts=2))
    m.commit(m.next_intent(), obs(1, xyz, f, 100.0))
    out = m.commit(m.next_intent(), None, failure="retryable")
    assert out["outcome"] == "rejected_evaluation"
    s = m.snapshot()
    assert (
        s["attempts"] == 2
        and s["failed_evaluations"] == 1
        and s["status"] == "objective_budget_exhausted"
    )
