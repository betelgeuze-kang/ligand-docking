from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "water_box_reference_v1",
    ROOT / "tools/run_engine_v2_water_box_reference_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
WATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATER)
PROFILE = WATER.load_profile(ROOT / "config/engine_v2_water_box_reference_v1.json")


def test_analytic_force_matches_finite_difference() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(PROFILE)
    energy, forces = WATER.energy_forces(
        PROFILE, positions, charges, atom_types, box
    )
    assert np.isfinite(energy)
    step = 1.0e-6
    numeric = np.zeros_like(forces)
    for atom in range(len(positions)):
        for axis in range(3):
            plus, minus = positions.copy(), positions.copy()
            plus[atom, axis] += step
            minus[atom, axis] -= step
            energy_plus, _ = WATER.energy_forces(
                PROFILE, plus, charges, atom_types, box
            )
            energy_minus, _ = WATER.energy_forces(
                PROFILE, minus, charges, atom_types, box
            )
            numeric[atom, axis] = -(energy_plus - energy_minus) / (2.0 * step)
    assert np.max(np.abs(numeric - forces)) < 2.0e-5


def test_checkpoint_continuation_is_exact() -> None:
    positions, masses, charges, atom_types, box = WATER.build_box(PROFILE)
    velocities = np.zeros_like(positions)
    velocities[1, 2] = 1.0e-4
    first_positions, first_velocities = positions.copy(), velocities.copy()
    for _ in range(100):
        first_positions, first_velocities, _ = WATER.step_verlet(
            PROFILE,
            first_positions,
            first_velocities,
            masses,
            charges,
            atom_types,
            box,
            0.02,
        )
    resumed_positions, resumed_velocities = positions.copy(), velocities.copy()
    for _ in range(50):
        resumed_positions, resumed_velocities, _ = WATER.step_verlet(
            PROFILE,
            resumed_positions,
            resumed_velocities,
            masses,
            charges,
            atom_types,
            box,
            0.02,
        )
    checkpoint_positions = resumed_positions.copy()
    checkpoint_velocities = resumed_velocities.copy()
    for _ in range(50):
        checkpoint_positions, checkpoint_velocities, _ = WATER.step_verlet(
            PROFILE,
            checkpoint_positions,
            checkpoint_velocities,
            masses,
            charges,
            atom_types,
            box,
            0.02,
        )
    assert np.array_equal(first_positions, checkpoint_positions)
    assert np.array_equal(first_velocities, checkpoint_velocities)


def test_small_timestep_nve_drift_is_bounded() -> None:
    result = WATER.run_nve(PROFILE, 100, 0.02)
    assert abs(result["absolute_drift"]) < 1.0e-5
    assert result["authority"]["production_md_validated"] is False


def test_nonfinite_state_is_rejected() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(PROFILE)
    positions[0, 0] = np.nan
    with pytest.raises(WATER.WaterReferenceError, match="nonfinite"):
        WATER.energy_forces(PROFILE, positions, charges, atom_types, box)


def test_unsupported_atom_type_is_rejected() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(PROFILE)
    atom_types[0] = 7
    with pytest.raises(WATER.WaterReferenceError, match="unsupported atom type"):
        WATER.energy_forces(PROFILE, positions, charges, atom_types, box)
