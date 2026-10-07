"""Independent 80-digit scalar-potential oracle; no product-derived forces.

Regenerate the committed fixture with tools/build_linear_angle_independent_oracle.py
(mpmath and NumPy required only for regeneration). CI consumes fixed numbers.
"""

import json
from pathlib import Path

import pytest
import torch

from betelgeuze_product.cpu_refinement_linear_angle_v1.geometry import (
    harmonic_linear_angle_energy,
)

ROWS = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures/linear_angle_independent_oracle.json"
    ).read_text()
)["cases"]


@pytest.mark.parametrize(
    "row",
    ROWS,
    ids=[f"eps={r['eps']}:plane={r['plane']}:rotation={r['rotation']}" for r in ROWS],
)
def test_independent_scalar_energy_cartesian_forces_and_conservation(row):
    xyz = torch.tensor([row["coords"]], dtype=torch.float64, requires_grad=True)
    energy = harmonic_linear_angle_energy(
        xyz[:, 0] - xyz[:, 1], xyz[:, 2] - xyz[:, 1], row["k"]
    )
    force = -torch.autograd.grad(energy.sum(), xyz)[0][0]
    expected = torch.tensor(row["forces"], dtype=torch.float64)
    torch.testing.assert_close(force, expected, rtol=2e-12, atol=3e-12)
    assert energy.item() == pytest.approx(row["energy"], rel=2e-12, abs=3e-13)
    torch.testing.assert_close(
        force.sum(0), torch.zeros(3, dtype=torch.float64), rtol=0.0, atol=1e-12
    )
    torque = torch.linalg.cross(xyz[0] - xyz[0, 1], force, dim=-1).sum(0)
    torch.testing.assert_close(
        torque, torch.zeros(3, dtype=torch.float64), rtol=0.0, atol=3e-12
    )
    if row["rotation"] == 0 and row["eps"] > 0:
        # Absolute tolerances alone could miss a tiny-angle force-clamping dead zone.
        assert (
            force - expected
        ).abs().max().item() <= expected.abs().max().item() * 2e-5 + 1e-28
        assert abs(energy.item() - row["energy"]) <= row["energy"] * 2e-5 + 1e-50


def test_endpoint_curvature_and_mixed_batch_gradients_are_regular():
    xyz = torch.tensor(
        [
            [[1.7, 0.0, 0.0], [0.0, 0.0, 0.0], [-0.61, 0.0, 0.0]],
            [[1.7, 0.0, 0.0], [0.0, 0.0, 0.0], [-0.6, 0.08, 0.09]],
        ],
        dtype=torch.float64,
        requires_grad=True,
    )
    energy = harmonic_linear_angle_energy(
        xyz[:, 0] - xyz[:, 1], xyz[:, 2] - xyz[:, 1], 17.0
    )
    force = -torch.autograd.grad(energy.sum(), xyz)[0]
    assert bool(torch.isfinite(force).all())
    assert torch.equal(force[0], torch.zeros_like(force[0]))

    def scalar(x):
        return harmonic_linear_angle_energy(
            x[None, :3] - x[None, 3:6], x[None, 6:] - x[None, 3:6], 17.0
        ).sum()

    hessian = torch.autograd.functional.hessian(scalar, xyz[0].detach().flatten())
    expected = torch.zeros((9, 9), dtype=torch.float64)
    # Independent transverse geometry: delta_y = y0/a - y1*(1/a+1/b) + y2/b.
    for axis in (1, 2):
        a = torch.zeros(9, dtype=torch.float64)
        a[axis], a[3 + axis], a[6 + axis] = 1 / 1.7, -(1 / 1.7 + 1 / 0.61), 1 / 0.61
        expected += 17.0 * torch.outer(a, a)
    assert bool(torch.isfinite(hessian).all())
    torch.testing.assert_close(hessian, expected, rtol=0.0, atol=1e-12)
