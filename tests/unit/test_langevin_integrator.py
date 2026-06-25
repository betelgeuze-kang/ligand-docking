from __future__ import annotations

import math

import pytest
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


def test_adaptive_timestep_multi_batch_updates_with_independent_dt() -> None:
    integrator = LangevinIntegrator(
        dt=0.01,
        friction=0.0,
        kT=0.0,
        adaptive_dt=True,
        dt_min=0.001,
        dt_max=0.02,
        force_threshold=10.0,
        mass=1.0,
    )
    c = torch.zeros((2, 1, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    f[0, 0, 0] = 5.0
    f[1, 0, 0] = 1000.0

    v_new, c_new = integrator.step(c, v, f, noise=torch.zeros_like(c))

    assert torch.allclose(integrator.last_dt.flatten(), torch.tensor([0.02, 0.001]))
    assert torch.allclose(v_new[:, 0, 0], torch.tensor([0.1, 1.0]))
    assert torch.allclose(c_new[:, 0, 0], torch.tensor([0.002, 0.001]))


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

    assert integrator.coarse_mass_policy == "explicit_mass_tensor"
    assert torch.allclose(v_new[0, 0], torch.full((3,), 0.01))
    assert torch.allclose(v_new[0, 1], torch.full((3,), 0.005))


def test_default_unit_mass_policy_is_explicit_when_mass_is_not_overridden() -> None:
    integrator = LangevinIntegrator()

    assert integrator.coarse_mass_policy == "explicit_unit_mass"
    assert torch.equal(integrator.mass, torch.tensor(1.0))


def test_step_matches_closed_form_reference_with_mass_and_external_noise() -> None:
    c = torch.tensor(
        [
            [[0.0, 1.0, -1.0], [2.0, -2.0, 0.5]],
            [[1.5, -0.5, 0.0], [-1.0, 0.25, 2.0]],
        ],
        dtype=torch.float32,
    )
    v = torch.tensor(
        [
            [[0.2, -0.1, 0.0], [0.3, 0.4, -0.2]],
            [[-0.5, 0.1, 0.25], [0.0, -0.3, 0.6]],
        ],
        dtype=torch.float32,
    )
    f = torch.tensor(
        [
            [[1.0, -2.0, 0.5], [-1.5, 0.75, 2.5]],
            [[0.25, 0.5, -0.75], [1.25, -1.0, 0.0]],
        ],
        dtype=torch.float32,
    )
    noise = torch.tensor(
        [
            [[0.01, -0.02, 0.03], [-0.04, 0.05, -0.01]],
            [[0.02, 0.01, -0.03], [0.0, -0.02, 0.04]],
        ],
        dtype=torch.float32,
    )
    mass = torch.tensor([[[1.0], [2.0]], [[4.0], [8.0]]], dtype=torch.float32)
    dt = 0.004
    gamma = 0.7
    integrator = LangevinIntegrator(
        dt=dt,
        friction=gamma,
        kT=0.0,
        mass=mass,
        coarse_mass_policy="explicit_mass_tensor",
    )

    v_new, c_new = integrator.step(c, v, f, noise=noise)

    decay = math.exp(-gamma * dt)
    force_scale = -math.expm1(-gamma * dt) / gamma
    expected_v = (v * decay) + (f * force_scale / mass) + noise
    expected_c = c + expected_v * dt
    assert torch.allclose(v_new, expected_v)
    assert torch.allclose(c_new, expected_c)
    assert integrator.coarse_mass_policy == "explicit_mass_tensor"


def test_mass_tensor_accepts_batched_atom_axis_and_rejects_invalid_mass() -> None:
    c = torch.zeros((2, 2, 3))
    v = torch.zeros_like(c)
    f = torch.ones_like(c)
    mass = torch.tensor([[[1.0], [2.0]], [[4.0], [8.0]]])
    integrator = LangevinIntegrator(
        dt=0.01,
        friction=0.0,
        kT=0.0,
        mass=mass,
        coarse_mass_policy="explicit_mass_tensor",
    )

    v_new, _ = integrator.step(c, v, f, noise=torch.zeros_like(c))

    assert torch.allclose(v_new[:, :, 0], torch.tensor([[0.01, 0.005], [0.0025, 0.00125]]))
    with pytest.raises(ValueError, match="mass values must be positive"):
        integrator.step(c, v, f, mass=torch.tensor([[1.0, 0.0], [1.0, 1.0]]))
    with pytest.raises(ValueError, match="mass trailing dimension must be 1"):
        integrator.step(c, v, f, mass=torch.ones((2, 2, 3)))
    with pytest.raises(ValueError, match="unsupported coarse_mass_policy"):
        LangevinIntegrator(coarse_mass_policy="implicit_unknown_mass")


def test_mass_tensor_scales_stochastic_noise_variance() -> None:
    dt = 0.002
    gamma = 1.5
    kT = 0.7
    atom_count = 8192
    mass = torch.ones((1, atom_count))
    mass[:, atom_count // 2 :] = 4.0
    c = torch.zeros((1, atom_count, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    integrator = LangevinIntegrator(dt=dt, friction=gamma, kT=kT, mass=mass, seed=5)

    v_new, _ = integrator.step(c, v, f)

    light_var = float(v_new[:, : atom_count // 2, :].var(unbiased=False).item())
    heavy_var = float(v_new[:, atom_count // 2 :, :].var(unbiased=False).item())
    expected_light = kT * (1.0 - math.exp(-2.0 * gamma * dt)) / 1.0
    expected_heavy = kT * (1.0 - math.exp(-2.0 * gamma * dt)) / 4.0
    assert abs(light_var - expected_light) / expected_light < 0.08
    assert abs(heavy_var - expected_heavy) / expected_heavy < 0.08
    assert abs(light_var / heavy_var - 4.0) < 0.35


def test_adaptive_timestep_scales_stochastic_variance_per_batch() -> None:
    dt = 0.01
    gamma = 1.2
    kT = 0.6
    atom_count = 12000
    c = torch.zeros((2, atom_count, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    f[0, :, 0] = 5.0
    f[1, :, 0] = 1000.0
    integrator = LangevinIntegrator(
        dt=dt,
        friction=gamma,
        kT=kT,
        adaptive_dt=True,
        dt_min=0.001,
        dt_max=0.02,
        force_threshold=10.0,
        seed=19,
    )

    v_new, _ = integrator.step(c, v, f)

    observed_dt = integrator.last_dt.flatten()
    force_scale = -torch.expm1(-torch.tensor(gamma) * observed_dt) / gamma
    residual = v_new - (f * force_scale.view(-1, 1, 1))
    expected_var = kT * (1.0 - torch.exp(-2.0 * gamma * observed_dt))
    observed_var = residual.var(dim=(1, 2), unbiased=False)
    assert torch.allclose(observed_dt, torch.tensor([0.02, 0.001]))
    assert torch.all(torch.abs(observed_var - expected_var) / expected_var < 0.08)


def test_heterogeneous_mass_equipartition_temperature_is_maintained() -> None:
    torch.manual_seed(4)
    kT = 0.9
    atom_count = 4096
    mass = torch.ones((1, atom_count))
    mass[:, atom_count // 2 :] = 4.0
    c = torch.zeros((1, atom_count, 3))
    v = torch.randn_like(c) * torch.sqrt(kT / mass.unsqueeze(-1))
    f = torch.zeros_like(c)
    integrator = LangevinIntegrator(
        dt=0.001,
        friction=1.0,
        kT=kT,
        mass=mass,
        coarse_mass_policy="explicit_mass_tensor",
        seed=17,
    )

    for _ in range(350):
        v, c = integrator.step(c, v, f)

    light_kT = float((mass[:, : atom_count // 2].unsqueeze(-1) * v[:, : atom_count // 2, :].pow(2)).mean().item())
    heavy_kT = float((mass[:, atom_count // 2 :].unsqueeze(-1) * v[:, atom_count // 2 :, :].pow(2)).mean().item())
    assert abs(light_kT - kT) / kT < 0.14
    assert abs(heavy_kT - kT) / kT < 0.14
    assert abs(light_kT - heavy_kT) / kT < 0.12


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


def test_seed_sequence_replays_after_reset_across_multiple_steps() -> None:
    c = torch.zeros((1, 16, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    a = LangevinIntegrator(dt=0.002, friction=1.0, kT=0.75, seed=123)
    b = LangevinIntegrator(dt=0.002, friction=1.0, kT=0.75, seed=123)

    a_trace = []
    b_trace = []
    for _ in range(3):
        v, c = a.step(c, v, f)
        a_trace.append(v.clone())
    c_b = torch.zeros_like(c)
    v_b = torch.zeros_like(v)
    for _ in range(3):
        v_b, c_b = b.step(c_b, v_b, f)
        b_trace.append(v_b.clone())
    for left, right in zip(a_trace, b_trace):
        assert torch.equal(left, right)

    a.set_seed(123)
    c_reset = torch.zeros_like(c)
    v_reset = torch.zeros_like(v)
    for expected in a_trace:
        v_reset, c_reset = a.step(c_reset, v_reset, f)
        assert torch.equal(v_reset, expected)


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
    observed_kT = float(v.pow(2).mean().item())
    assert abs(observed_var - (kT / k)) / (kT / k) < 0.25
    assert abs(observed_kT - kT) / kT < 0.25


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


def test_mixed_precision_tracks_fp32_with_supplied_stochastic_noise_and_mass() -> None:
    c = torch.linspace(-0.5, 0.75, 24).view(2, 4, 3)
    v = torch.linspace(-0.4, 0.4, 24).view(2, 4, 3)
    f = torch.cos(c)
    noise = torch.linspace(-0.03, 0.03, 24).view(2, 4, 3)
    mass = torch.tensor([[1.0, 2.0, 4.0, 8.0], [1.5, 2.5, 3.5, 4.5]])
    fp32 = LangevinIntegrator(
        dt=0.0015,
        friction=0.6,
        kT=0.7,
        mass=mass,
        coarse_mass_policy="explicit_mass_tensor",
    )
    fp16 = LangevinIntegrator(
        dt=0.0015,
        friction=0.6,
        kT=0.7,
        mass=mass,
        coarse_mass_policy="explicit_mass_tensor",
        use_mixed_precision=True,
    )

    v32, c32 = fp32.step(c, v, f, noise=noise)
    v16, c16 = fp16.step(c, v, f, noise=noise)

    assert torch.max(torch.abs(v32 - v16)).item() < 3e-3
    assert torch.max(torch.abs(c32 - c16)).item() < 3e-3


def test_mixed_precision_internal_stochastic_noise_matches_fp32_distribution() -> None:
    dt = 0.002
    gamma = 1.25
    kT = 0.8
    c = torch.zeros((1, 16384, 3))
    v = torch.zeros_like(c)
    f = torch.zeros_like(c)
    fp32 = LangevinIntegrator(dt=dt, friction=gamma, kT=kT, seed=1234)
    fp16 = LangevinIntegrator(dt=dt, friction=gamma, kT=kT, seed=5678, use_mixed_precision=True)

    v32, _ = fp32.step(c, v, f)
    v16, _ = fp16.step(c, v, f)

    expected_variance = kT * (1.0 - math.exp(-2.0 * gamma * dt))
    var32 = float(v32.var(unbiased=False).item())
    var16 = float(v16.float().var(unbiased=False).item())
    assert abs(var32 - expected_variance) / expected_variance < 0.08
    assert abs(var16 - expected_variance) / expected_variance < 0.10
    assert abs(var32 - var16) / expected_variance < 0.12
