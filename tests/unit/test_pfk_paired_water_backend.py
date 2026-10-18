"""Synthetic WL adapter checks using the exact source-admitted original kernel.

The numerical cases require the recovered source, optionally selected with
PFK_ORIGINAL_WATER_SOURCE_ROOT. Missing external source skips those cases; it is
never replaced with a reimplemented potential or real prepared molecular input.
"""

import hashlib
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import torch

from tools.pfk_paired_water_eight_dof.backend import (
    MobileLigandWaterTerms, UnresolvedWaterWork,
)


SETTINGS = dict(cutoff_angstrom=10., switch_start_angstrom=8.,
                minimum_distance_angstrom=.35, dielectric=1.,
                screening_kappa_per_angstrom=0., receptor_block_size=128,
                mixing_rule="lorentz_berthelot", periodic=False)
LIGAND = ((3.1, .12, -.3), (2.8, .08, .2))
WATER = ((3.15061, .15209990439770554, -.834), (0., 0., .417), (0., 0., .417))
SOURCE = Path(os.environ.get("PFK_ORIGINAL_WATER_SOURCE_ROOT", (
    "/home/betelgeuze/Documents/Codex/2026-10-18/task/"
    "recover_362_20261018_IFbvbU/restored/"
    "water-global-fixed-chart-return-optimizer-preflight-20261017/adapter"
)))
HASHES = {
    "pair_kernel": "0e0b274525df5f4f3e1f4885eb0e875a9b8ed5bf2e3c274eb3741f9758593838",
    "coulomb_force_taper_kernel": "e64542a2cecc40040b81cf8b59136c5941751c618a51f1551ec43fe590272941",
}


@pytest.fixture
def original_kernel(monkeypatch):
    if not SOURCE.is_dir():
        pytest.skip("exact recovered original water kernel source is unavailable")
    modules = {}
    for name in ("coulomb_force_taper_kernel", "pair_kernel"):
        path = SOURCE / (name + ".py")
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == HASHES[name], "unadmitted original source"
        module = ModuleType(name)
        module.__file__ = str(path)
        monkeypatch.setitem(sys.modules, name, module)
        # Compile verified bytes directly: no archive bytecode or cache writes.
        exec(compile(raw, str(path), "exec"), module.__dict__)
        modules[name] = module
    return modules["pair_kernel"]._evaluate_validated_cross_terms


def positions(distance=4.):
    ligand = torch.tensor([[0., 0., 0.], [1.2, .4, -.2]], dtype=torch.float64)
    water = torch.tensor([[distance, 0., 0.], [distance+.9572, 0., 0.],
                          [distance-.24, .926, 0.]], dtype=torch.float64)
    return ligand, water


def adapter(kernel, water, observer=None, parameters=WATER):
    return MobileLigandWaterTerms(kernel, LIGAND, water, parameters, SETTINGS, observer)


def direct(kernel, mobile, fixed, mobile_parameters, fixed_parameters):
    rows = tuple(SimpleNamespace(sigma_angstrom=s, epsilon_kcal_per_mol=e, charge_e=q)
                 for s, e, q in fixed_parameters)
    context = SimpleNamespace(
        receptor=SimpleNamespace(coordinates=fixed.unsqueeze(0), atom_count=len(fixed)),
        cross=SimpleNamespace(**SETTINGS, receptor_atoms=rows), assert_intact=lambda: None,
    )
    params = tuple(SimpleNamespace(sigma_angstrom=s, epsilon_kcal_per_mol=e, charge_e=q)
                   for s, e, q in mobile_parameters)
    return kernel(context, SimpleNamespace(coordinates=mobile.unsqueeze(0)), params)


def test_original_parity_and_reservation_order(original_kernel):
    x, water = positions()
    expected, forces, pairs = direct(original_kernel, x, water, LIGAND, WATER)
    events = []
    terms = adapter(original_kernel, water, lambda *row: events.append(row))
    result = terms.evaluate(x)
    assert result.components["WL_LJ"] == float(expected["cross_lennard_jones"][0])
    assert result.components["WL_Coulomb"] == float(expected["cross_screened_coulomb"][0])
    assert torch.equal(result.forces, forces[0])
    assert result.active_pairs == pairs == 6
    assert dict(result.work) == dict(kernel_calls=1, backward_calls=1,
                                    total_work_known=True, unknown_work_reissued=False)
    assert events == [("WL_EF", "started", None), ("backward_WL", "started", None),
                      ("backward_WL", "finished", True), ("WL_EF", "finished", True)]


@pytest.mark.parametrize("distance", [4., 9.1, 11.5])
def test_returned_force_is_negative_energy_gradient(original_kernel, distance):
    x, water = positions(distance)
    terms = adapter(original_kernel, water)
    force = terms.evaluate(x).forces
    numerical = torch.zeros_like(x)
    h = 1e-5
    for atom in range(len(x)):
        for axis in range(3):
            plus, minus = x.clone(), x.clone()
            plus[atom, axis] += h
            minus[atom, axis] -= h
            numerical[atom, axis] = -(terms.evaluate(plus).energy - terms.evaluate(minus).energy)/(2*h)
    torch.testing.assert_close(force, numerical, rtol=2e-6, atol=2e-7)


def test_pair_forces_obey_action_reaction(original_kernel):
    x, water = positions(9.1)
    ligand_force = adapter(original_kernel, water).evaluate(x).forces
    _, water_force, _ = direct(original_kernel, water, x, WATER, LIGAND)
    torch.testing.assert_close(ligand_force.sum(0) + water_force[0].sum(0),
                               torch.zeros(3, dtype=torch.float64), rtol=0., atol=1e-11)


def test_actual_backward_count_tracks_active_original_blocks(original_kernel):
    x, water = positions()
    terms = adapter(original_kernel, water.repeat(43, 1), parameters=WATER * 43)
    first = terms.evaluate(x)
    assert first.work["backward_calls"] == 2
    assert first.active_pairs == 2 * 129
    second = terms.evaluate(x + 100.)
    assert second.energy == 0. and torch.count_nonzero(second.forces) == 0
    assert second.work["backward_calls"] == 0 and second.work["kernel_calls"] == 1
    assert terms.work_snapshot()["stages"]["WL_EF"]["dispatched"] == 2


@pytest.mark.parametrize("event", ["started", "finished"])
def test_observer_failure_is_unknown_and_cannot_reissue(original_kernel, event):
    x, water = positions()
    grad = torch.autograd.grad
    events = []

    def observer(kind, phase, success):
        events.append((kind, phase, success))
        if kind == "backward_WL" and phase == event:
            raise OSError("injected observer fsync failure")

    terms = adapter(original_kernel, water, observer)
    with pytest.raises(UnresolvedWaterWork):
        terms.evaluate(x)
    assert torch.autograd.grad is grad
    saved = terms.work_snapshot()
    assert saved["poisoned"] and not saved["total_work_known"]
    assert saved["total_kernel_calls"] is saved["total_backward_calls"] is None
    assert saved["stages"]["WL_EF"]["pending"] == 1
    backward = saved["stages"]["backward_WL"]
    assert backward["pending"] == 1
    assert backward["dispatched"] == int(event == "finished")
    assert backward["returned"] == int(event == "finished")
    assert ("WL_EF", "finished", False) not in events
    with pytest.raises(RuntimeError, match="cannot be retried"):
        terms.evaluate(x)
    assert saved == terms.work_snapshot()


def test_reservation_failure_precedes_original_dispatch(original_kernel):
    x, water = positions()
    called = []

    def kernel(*args):
        called.append(True)
        return original_kernel(*args)

    def observer(*args):
        raise OSError("reservation durability unknown")

    terms = adapter(kernel, water, observer)
    with pytest.raises(UnresolvedWaterWork):
        terms.evaluate(x)
    assert called == []
    assert terms.work_snapshot()["stages"]["WL_EF"]["dispatched"] == 0


def test_original_applicability_failure_is_retained_and_poisoned(original_kernel):
    x, water = positions()
    x[0] = water[0] + .01
    events = []
    terms = adapter(original_kernel, water, lambda *row: events.append(row))
    grad = torch.autograd.grad
    with pytest.raises(ValueError, match="minimum distance"):
        terms.evaluate(x)
    assert torch.autograd.grad is grad
    work = terms.work_snapshot()
    assert work["poisoned"] and work["total_work_known"]
    assert work["stages"]["WL_EF"]["failed"] == 1
    assert work["stages"]["backward_WL"]["dispatched"] == 0
    assert events[-1] == ("WL_EF", "finished", False)


def test_baseexception_keeps_unknown_reservation_and_restores_grad(original_kernel):
    x, water = positions()
    grad = torch.autograd.grad

    def killed(*args):
        raise KeyboardInterrupt("synthetic interruption")

    terms = adapter(killed, water)
    with pytest.raises(KeyboardInterrupt):
        terms.evaluate(x)
    assert torch.autograd.grad is grad
    assert not terms.work_snapshot()["total_work_known"]
    assert terms.work_snapshot()["stages"]["WL_EF"]["pending"] == 1


def test_fixed_input_is_cloned_and_internal_mutation_rejected(original_kernel):
    x, water = positions()
    terms = adapter(original_kernel, water)
    water.add_(100.)
    assert terms.evaluate(x).energy != 0.
    terms._fixed.add_(1.)
    with pytest.raises(ValueError, match="fixed water"):
        terms.evaluate(x)


def test_fixed_parameter_mutation_cannot_alias_frozen_identity(original_kernel):
    x, water = positions()
    terms = adapter(original_kernel, water)
    object.__setattr__(terms._water[0], "charge_e", -.8)
    with pytest.raises(ValueError, match="parameters/settings changed"):
        terms.evaluate(x)
    assert terms.work_snapshot()["known_kernel_calls"] == 0


@pytest.mark.parametrize("bad", [dict(SETTINGS, receptor_block_size=64),
                                  dict(SETTINGS, dielectric=2.),
                                  dict(SETTINGS, dielectric=True),
                                  dict(SETTINGS, periodic=0),
                                  dict(SETTINGS, unknown_policy=True)])
def test_unadmitted_settings_rejected_without_dispatch(bad):
    _, water = positions()
    with pytest.raises(ValueError):
        MobileLigandWaterTerms(lambda *a: pytest.fail("unexpected evaluation"),
                              LIGAND, water, WATER, bad)


@pytest.mark.parametrize("rows", [[(0., .1, 0.)], [(1., .1, float("nan"))],
                                   [dict(sigma_angstrom=1., epsilon_kcal_per_mol=.1,
                                         charge_e=0., atom_index=2)]])
def test_invalid_parameter_metadata_rejected_without_dispatch(rows):
    _, water = positions()
    with pytest.raises(ValueError):
        MobileLigandWaterTerms(lambda *a: pytest.fail("unexpected evaluation"),
                              rows, water, WATER, SETTINGS)


def test_foreign_grad_instrumentation_is_not_overwritten(original_kernel, monkeypatch):
    x, water = positions()

    def foreign(*args, **kwargs):
        pytest.fail("foreign instrument dispatched")

    monkeypatch.setattr(torch.autograd, "grad", foreign)
    terms = adapter(original_kernel, water)
    with pytest.raises(RuntimeError, match="overlaps"):
        terms.evaluate(x)
    assert torch.autograd.grad is foreign
    assert terms.work_snapshot()["stages"]["WL_EF"]["dispatched"] == 0
