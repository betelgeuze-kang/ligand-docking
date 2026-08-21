from __future__ import annotations

import hashlib
import importlib.util
import json
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
NATIVE_PROFILE = WATER.load_profile(
    ROOT / "config/engine_v2_native_water_box_profile_v1.json"
)
CONSTRAINTS_PROFILE = json.loads(
    (ROOT / "config/engine_v2_native_water_box_constraints_profile_v1.json").read_text()
)


def test_native_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
    )


def test_native_constraints_profile_matches_the_packaged_runtime_asset() -> None:
    canonical = (
        ROOT / "config/engine_v2_native_water_box_constraints_profile_v1.json"
    ).read_bytes()
    packaged = (
        ROOT
        / "rust/betelgeuze-runtime/assets/engine_v2_native_water_box_constraints_profile_v1.json"
    ).read_bytes()
    assert packaged == canonical
    assert hashlib.sha256(canonical).hexdigest() == (
        "8dcad0b5005b7a768ce0a88b1804b55ecddb9b3490e2dd59179dfa2393433507"
    )
    assert CONSTRAINTS_PROFILE["predecessor"]["sha256"] == (
        "2b0be83b57085c655092ab0272aea5a91b9c3f90c344fa062d494ad324f0019e"
    )
    constraints = CONSTRAINTS_PROFILE["constraints"]
    assert constraints["rows_per_water"] * constraints["water_count"] == 6
    positions, *_ = WATER.build_box(NATIVE_PROFILE)
    assert constraints["hh_distance_angstrom"] == pytest.approx(
        np.linalg.norm(positions[1] - positions[2]), abs=1.0e-15
    )
    assert constraints["expected_degrees_of_freedom"] == 12
    assert all(value is False for value in CONSTRAINTS_PROFILE["authority"].values())


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


def test_native_profile_matches_the_frozen_initial_energy_and_force() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(NATIVE_PROFILE)
    energy, forces = WATER.energy_forces(
        NATIVE_PROFILE, positions, charges, atom_types, box
    )
    assert energy == pytest.approx(-2.235452238349433, abs=2.0e-14)
    assert forces[0, 0] == pytest.approx(-3.7730687065767325, abs=2.0e-14)
    assert forces[4, 1] == pytest.approx(0.246800271365888, abs=2.0e-14)


def test_native_profile_freezes_the_100_step_nve_observation() -> None:
    result = WATER.run_nve(NATIVE_PROFILE, 100, 0.02)
    repeated = WATER.run_nve(NATIVE_PROFILE, 100, 0.02)
    assert result["initial_total_energy"] == pytest.approx(
        -2.2354281465712305, abs=2.0e-14
    )
    assert result["final_total_energy"] == pytest.approx(
        -2.2354282714680176, abs=2.0e-14
    )
    assert result["absolute_drift"] == pytest.approx(
        -1.2489678713478725e-7, abs=2.0e-14
    )
    assert result["checkpoint_sha256"] == repeated["checkpoint_sha256"]
    assert len(result["checkpoint_sha256"]) == 64
    int(result["checkpoint_sha256"], 16)


def test_native_switch_force_matches_finite_difference() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(NATIVE_PROFILE)
    positions[3:] += np.array([2.7, 0.0, 0.0])
    _energy, forces = WATER.energy_forces(
        NATIVE_PROFILE, positions, charges, atom_types, box
    )
    step = 1.0e-6
    plus, minus = positions.copy(), positions.copy()
    plus[3, 0] += step
    minus[3, 0] -= step
    energy_plus, _ = WATER.energy_forces(
        NATIVE_PROFILE, plus, charges, atom_types, box
    )
    energy_minus, _ = WATER.energy_forces(
        NATIVE_PROFILE, minus, charges, atom_types, box
    )
    numeric = -(energy_plus - energy_minus) / (2.0 * step)
    assert forces[3, 0] == pytest.approx(numeric, abs=2.0e-5)


def test_native_cutoff_removes_all_interwater_pairs() -> None:
    positions, _masses, charges, atom_types, box = WATER.build_box(NATIVE_PROFILE)
    positions[3:] += np.array([3.0, 7.0, 7.0])
    energy, forces = WATER.energy_forces(
        NATIVE_PROFILE, positions, charges, atom_types, box
    )
    assert abs(energy) < 1.0e-24
    assert np.max(np.abs(forces)) < 1.0e-12


def test_native_nonbonded_settings_fail_closed() -> None:
    profile = {**NATIVE_PROFILE, "nonbonded": {"cutoff_angstrom": 7.0}}
    positions, _masses, charges, atom_types, box = WATER.build_box(profile)
    with pytest.raises(WATER.WaterReferenceError, match="incomplete"):
        WATER.energy_forces(profile, positions, charges, atom_types, box)
