from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "water_ref", ROOT / "tools/run_engine_v2_water_box_reference_v1.py"
)
assert SPEC is not None and SPEC.loader is not None
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)
PROFILE = W.load_profile(ROOT / "config/engine_v2_water_box_reference_v1.json")


def test_analytic_force_matches_finite_difference() -> None:
    positions, _masses, charges, types, box = W.build_box(PROFILE)
    energy, forces = W.energy_forces(PROFILE, positions, charges, types, box)
    assert np.isfinite(energy)
    step = 1e-6
    numeric = np.zeros_like(forces)
    for atom in range(len(positions)):
        for axis in range(3):
            plus, minus = positions.copy(), positions.copy()
            plus[atom, axis] += step
            minus[atom, axis] -= step
            ep, _ = W.energy_forces(PROFILE, plus, charges, types, box)
            em, _ = W.energy_forces(PROFILE, minus, charges, types, box)
            numeric[atom, axis] = -(ep - em) / (2 * step)
    assert np.max(np.abs(numeric - forces)) < 2e-5


def test_checkpoint_continuation_is_exact() -> None:
    positions, masses, charges, types, box = W.build_box(PROFILE)
    velocities = np.zeros_like(positions)
    velocities[1, 2] = 1e-4
    a_pos, a_vel = positions.copy(), velocities.copy()
    for _ in range(100):
        a_pos, a_vel, _ = W.step_verlet(PROFILE, a_pos, a_vel, masses, charges, types, box, 0.02)
    b_pos, b_vel = positions.copy(), velocities.copy()
    for _ in range(50):
        b_pos, b_vel, _ = W.step_verlet(PROFILE, b_pos, b_vel, masses, charges, types, box, 0.02)
    checkpoint_pos, checkpoint_vel = b_pos.copy(), b_vel.copy()
    for _ in range(50):
        checkpoint_pos, checkpoint_vel, _ = W.step_verlet(
            PROFILE, checkpoint_pos, checkpoint_vel, masses, charges, types, box, 0.02
        )
    assert np.array_equal(a_pos, checkpoint_pos)
    assert np.array_equal(a_vel, checkpoint_vel)


def test_small_step_nve_drift_is_bounded() -> None:
    result = W.run_nve(PROFILE, 100, 0.02)
    assert abs(result["absolute_drift"]) < 1e-5
    assert result["authority"]["production_md_validated"] is False
