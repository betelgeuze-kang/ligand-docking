from __future__ import annotations

import torch

from core.integrator import LangevinIntegrator


def test_adaptive_timestep_single_batch_records_batch_dt() -> None:
    integrator = LangevinIntegrator(
        dt=0.01,
        adaptive_dt=True,
        dt_min=0.001,
        dt_max=0.02,
        force_threshold=10.0,
        seed=1,
    )
    c = torch.zeros((1, 3, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    f[0, 0, 0] = 5.0

    integrator.step(c, v, f)

    assert integrator.last_dt.shape == (1, 1, 1)
    assert torch.allclose(integrator.last_dt.flatten(), torch.tensor([0.02]))


def test_adaptive_timestep_multi_batch_is_independent_per_sample() -> None:
    integrator = LangevinIntegrator(
        dt=0.01,
        adaptive_dt=True,
        dt_min=0.001,
        dt_max=0.02,
        force_threshold=10.0,
        seed=1,
    )
    c = torch.zeros((2, 3, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    f[0, 0, 0] = 5.0
    f[1, 0, 0] = 1000.0

    integrator.step(c, v, f)

    assert integrator.last_dt.shape == (2, 1, 1)
    assert torch.allclose(integrator.last_dt.flatten(), torch.tensor([0.02, 0.001]))


def test_seed_reproducibility_for_stochastic_step() -> None:
    c = torch.zeros((4, 5, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    a = LangevinIntegrator(dt=0.002, friction=1.0, kT=0.75, seed=123)
    b = LangevinIntegrator(dt=0.002, friction=1.0, kT=0.75, seed=123)

    av, ac = a.step(c, v, f)
    bv, bc = b.step(c, v, f)

    assert torch.equal(av, bv)
    assert torch.equal(ac, bc)


def test_mass_tensor_scales_force_and_noise_variance() -> None:
    c = torch.zeros((1, 2, 3))
    v = torch.zeros_like(c)
    f = torch.ones_like(c)
    mass = torch.tensor([[1.0, 2.0]])
    integrator = LangevinIntegrator(dt=0.01, friction=0.0, kT=0.0, mass=mass)

    v_new, _ = integrator.step(c, v, f)

    assert integrator.coarse_mass_policy == "explicit_unit_mass"
    assert torch.allclose(v_new[0, 0], torch.full((3,), 0.01))
    assert torch.allclose(v_new[0, 1], torch.full((3,), 0.005))


def test_maxwell_boltzmann_temperature_is_maintained() -> None:
    torch.manual_seed(0)
    kT = 1.25
    mass = 2.0
    integrator = LangevinIntegrator(dt=0.001, friction=1.0, kT=kT, mass=mass, seed=7)
    c = torch.zeros((1, 4096, 3))
    v = torch.randn_like(c) * (kT / mass) ** 0.5
    f = torch.zeros_like(c)

    for _ in range(300):
        v, c = integrator.step(c, v, f)

    observed_kT = float((mass * v.pow(2)).mean().item())
    assert abs(observed_kT - kT) / kT < 0.12


def test_harmonic_energy_drift_and_equilibrium_distribution_are_bounded() -> None:
    k = 1.0
    c = torch.tensor([[[1.0, 0.0, 0.0]]])
    v = torch.tensor([[[0.0, 1.0, 0.0]]])
    integrator = LangevinIntegrator(dt=0.001, friction=0.0, kT=0.0)

    def energy(coords: torch.Tensor, vel: torch.Tensor) -> torch.Tensor:
        return 0.5 * k * coords.pow(2).sum() + 0.5 * vel.pow(2).sum()

    e0 = float(energy(c, v))
    for _ in range(1000):
        f = -k * c
        v, c = integrator.step(c, v, f)
    e1 = float(energy(c, v))
    assert abs(e1 - e0) / e0 < 0.01

    kT = 0.8
    torch.manual_seed(123)
    sampler = LangevinIntegrator(dt=0.001, friction=2.0, kT=kT, seed=11)
    c = torch.randn((1, 4096, 3)) * (kT / k) ** 0.5
    v = torch.randn_like(c) * kT**0.5
    for _ in range(600):
        f = -k * c
        v, c = sampler.step(c, v, f)

    observed_var = float(c.var(unbiased=False).item())
    assert abs(observed_var - (kT / k)) / (kT / k) < 0.25


def test_mixed_precision_tracks_fp32_for_deterministic_step() -> None:
    c = torch.linspace(0.0, 1.0, 24).view(2, 4, 3)
    v = torch.linspace(-0.2, 0.2, 24).view(2, 4, 3)
    f = torch.sin(c)
    noise = torch.zeros_like(c)
    fp32 = LangevinIntegrator(dt=0.002, friction=0.4, kT=0.0, mass=torch.ones((2, 4)))
    fp16 = LangevinIntegrator(
        dt=0.002,
        friction=0.4,
        kT=0.0,
        mass=torch.ones((2, 4)),
        use_mixed_precision=True,
    )

    v32, c32 = fp32.step(c, v, f, noise=noise)
    v16, c16 = fp16.step(c, v, f, noise=noise)

    assert torch.max(torch.abs(v32 - v16)).item() < 2e-3
    assert torch.max(torch.abs(c32 - c16)).item() < 2e-3
