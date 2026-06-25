from __future__ import annotations

import math

import pytest
import torch

from core.integrator import LangevinIntegrator


def test_adaptive_timestep_is_independent_per_batch_member() -> None:
    integrator = LangevinIntegrator(
        dt=1.0,
        friction=0.0,
        kT=0.0,
        adaptive_dt=True,
        dt_min=0.1,
        dt_max=2.0,
        force_threshold=10.0,
    )
    c = torch.zeros((2, 1, 3), dtype=torch.float64)
    v = torch.zeros_like(c)
    f = torch.tensor([[[1.0, 0.0, 0.0]], [[20.0, 0.0, 0.0]]], dtype=torch.float64)

    v_new, c_new = integrator.step(c, v, f, noise=torch.zeros_like(v))

    # Batch 0 uses dt=2.0; batch 1 uses dt=0.5.
    assert v_new[:, 0, 0].tolist() == pytest.approx([2.0, 10.0])
    assert c_new[:, 0, 0].tolist() == pytest.approx([4.0, 5.0])


def test_generated_noise_uses_full_langevin_variance(monkeypatch: pytest.MonkeyPatch) -> None:
    dt = 0.25
    gamma = 2.0
    kT = 3.0
    integrator = LangevinIntegrator(dt=dt, friction=gamma, kT=kT)
    c = torch.zeros((1, 1, 3), dtype=torch.float64)
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)

    # The integrator samples the stochastic increment via ``torch.randn`` with a
    # seeded generator; pin it to ones so the scaled noise std is observable.
    def _ones(shape, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return torch.ones(shape, dtype=kwargs.get("dtype"), device=kwargs.get("device"))

    monkeypatch.setattr(torch, "randn", _ones)
    v_new, c_new = integrator.step(c, v, f)

    # Exact-OU stochastic increment for unit mass:
    # std = sqrt(kT / mass * (1 - exp(-2 * gamma * dt))).
    expected_increment = math.sqrt(kT * (1.0 - math.exp(-2.0 * gamma * dt)))
    assert v_new.flatten().tolist() == pytest.approx([expected_increment] * 3)
    assert c_new.flatten().tolist() == pytest.approx([expected_increment * dt] * 3)


def test_supplied_noise_remains_a_pre_scaled_velocity_increment() -> None:
    integrator = LangevinIntegrator(dt=0.1, friction=0.0, kT=0.0)
    c = torch.zeros((1, 2, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    noise = torch.full_like(c, 0.25)

    v_new, c_new = integrator.step(c, v, f, noise=noise)

    assert torch.allclose(v_new, noise)
    assert torch.allclose(c_new, noise * 0.1)


def test_state_and_parameter_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="dt must be positive"):
        LangevinIntegrator(dt=0.0)
    with pytest.raises(ValueError, match="dt_max"):
        LangevinIntegrator(dt_min=0.01, dt_max=0.001)

    integrator = LangevinIntegrator()
    c = torch.zeros((1, 2, 3))
    with pytest.raises(ValueError, match="v shape"):
        integrator.step(c, torch.zeros((1, 1, 3)), torch.zeros_like(c))
    with pytest.raises(ValueError, match="noise shape"):
        integrator.step(c, torch.zeros_like(c), torch.zeros_like(c), noise=torch.zeros((1, 1, 3)))


def test_mixed_precision_contract_returns_finite_fp32_outputs() -> None:
    integrator = LangevinIntegrator(
        dt=0.002,
        friction=1.0,
        kT=0.0,
        use_mixed_precision=True,
    )
    c = torch.zeros((1, 2, 3), dtype=torch.float32)
    v = torch.zeros_like(c)
    f = torch.full_like(c, 0.5)

    v_new, c_new = integrator.step(c, v, f, noise=torch.zeros_like(v))

    assert v_new.dtype == torch.float32
    assert c_new.dtype == torch.float32
    assert torch.isfinite(v_new).all()
    assert torch.isfinite(c_new).all()
