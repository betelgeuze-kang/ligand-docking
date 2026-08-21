#!/usr/bin/env python3
"""Small deterministic CPU water-box development reference; no PME/NPT claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

PROFILE_SCHEMAS = {
    "betelgeuze.engine_v2_water_box_reference_profile/1.0.0",
    "betelgeuze.engine_v2_native_water_box_profile/1.0.0",
}


class WaterReferenceError(ValueError):
    """Water reference input is malformed or outside the bounded profile."""


def load_profile(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WaterReferenceError(f"cannot load water profile: {exc}") from exc
    if value.get("schema_id") not in PROFILE_SCHEMAS:
        raise WaterReferenceError("water profile schema changed")
    authority = value.get("authority")
    if type(authority) is not dict or any(
        state is not False for state in authority.values()
    ):
        raise WaterReferenceError("water authority escalated")
    return value


def water_geometry(profile: dict[str, Any]) -> np.ndarray:
    water = profile["water"]
    distance = float(water["oh_distance_angstrom"])
    half_angle = math.radians(float(water["hoh_angle_degrees"])) / 2.0
    return np.array(
        [
            [0.0, 0.0, 0.0],
            [
                distance * math.cos(half_angle),
                distance * math.sin(half_angle),
                0.0,
            ],
            [
                distance * math.cos(half_angle),
                -distance * math.sin(half_angle),
                0.0,
            ],
        ],
        dtype=np.float64,
    )


def build_box(
    profile: dict[str, Any],
    count: int = 2,
    spacing: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    if type(count) is not int or count < 1:
        raise WaterReferenceError("water count must be a positive integer")
    if not math.isfinite(spacing) or spacing <= 0.0:
        raise WaterReferenceError("water spacing must be positive and finite")
    geometry = water_geometry(profile)
    positions = np.vstack(
        [geometry + np.array([index * spacing, 0.0, 0.0]) for index in range(count)]
    )
    water = profile["water"]
    masses = np.tile(
        [
            water["oxygen_mass_dalton"],
            water["hydrogen_mass_dalton"],
            water["hydrogen_mass_dalton"],
        ],
        count,
    ).astype(float)
    charges = np.tile(
        [
            water["oxygen_charge"],
            water["hydrogen_charge"],
            water["hydrogen_charge"],
        ],
        count,
    ).astype(float)
    atom_types = np.tile([0, 1, 1], count)
    box = max(12.0, count * spacing + 6.0)
    return positions, masses, charges, atom_types, box


def minimum_image(delta: np.ndarray, box: float) -> np.ndarray:
    return delta - box * np.floor(delta / box + 0.5)


def _nonbonded_settings(
    profile: dict[str, Any],
) -> tuple[float | None, float | None, float, float, float]:
    value = profile.get("nonbonded")
    if value is None:
        return None, None, 1.0, 0.0, 1.0e-10
    if type(value) is not dict:
        raise WaterReferenceError("nonbonded settings must be an object")
    try:
        cutoff = float(value["cutoff_angstrom"])
        switch_start = float(value["switch_start_angstrom"])
        dielectric = float(value["dielectric"])
        screening_kappa = float(value["screening_kappa_per_angstrom"])
        minimum_distance = float(value["minimum_pair_distance_angstrom"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WaterReferenceError("nonbonded settings are incomplete") from exc
    if (
        not math.isfinite(cutoff)
        or cutoff <= 0.0
        or not math.isfinite(switch_start)
        or switch_start < 0.0
        or switch_start >= cutoff
        or not math.isfinite(dielectric)
        or dielectric <= 0.0
        or not math.isfinite(screening_kappa)
        or screening_kappa < 0.0
        or not math.isfinite(minimum_distance)
        or minimum_distance <= 0.0
    ):
        raise WaterReferenceError("nonbonded settings are invalid")
    return cutoff, switch_start, dielectric, screening_kappa, minimum_distance


def _switching_value(
    distance: float, start: float | None, cutoff: float | None
) -> tuple[float, float]:
    if start is None or cutoff is None or distance <= start:
        return 1.0, 0.0
    if distance >= cutoff:
        return 0.0, 0.0
    width = cutoff - start
    coordinate = (distance - start) / width
    coordinate2 = coordinate * coordinate
    coordinate3 = coordinate2 * coordinate
    coordinate4 = coordinate3 * coordinate
    coordinate5 = coordinate4 * coordinate
    return (
        1.0
        - 10.0 * coordinate3
        + 15.0 * coordinate4
        - 6.0 * coordinate5,
        (
            -30.0 * coordinate2
            + 60.0 * coordinate3
            - 30.0 * coordinate4
        )
        / width,
    )


def energy_forces(
    profile: dict[str, Any],
    positions: np.ndarray,
    charges: np.ndarray,
    atom_types: np.ndarray,
    box: float,
) -> tuple[float, np.ndarray]:
    positions = np.asarray(positions, dtype=np.float64)
    charges = np.asarray(charges, dtype=np.float64)
    atom_types = np.asarray(atom_types, dtype=np.int64)
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) % 3:
        raise WaterReferenceError("positions must contain complete waters")
    if len(charges) != len(positions) or len(atom_types) != len(positions):
        raise WaterReferenceError("per-atom input length mismatch")
    if not np.isfinite(positions).all() or not np.isfinite(charges).all():
        raise WaterReferenceError("nonfinite state")
    if not math.isfinite(box) or box <= 0.0:
        raise WaterReferenceError("box must be positive and finite")
    forces = np.zeros_like(positions)
    energy = 0.0
    water = profile["water"]
    equilibrium_distance = float(water["oh_distance_angstrom"])
    equilibrium_angle = math.radians(float(water["hoh_angle_degrees"]))
    bond_k = float(water["bond_k_kcal_per_mol_a2"])
    angle_k = float(water["angle_k_kcal_per_mol_rad2"])

    for base in range(0, len(positions), 3):
        oxygen, hydrogen1, hydrogen2 = base, base + 1, base + 2
        for hydrogen in (hydrogen1, hydrogen2):
            displacement = positions[hydrogen] - positions[oxygen]
            distance = float(np.linalg.norm(displacement))
            if distance <= 1.0e-12:
                raise WaterReferenceError("degenerate bond")
            delta = distance - equilibrium_distance
            energy += 0.5 * bond_k * delta * delta
            force = bond_k * delta * displacement / distance
            forces[oxygen] += force
            forces[hydrogen] -= force

        vector1 = positions[hydrogen1] - positions[oxygen]
        vector2 = positions[hydrogen2] - positions[oxygen]
        length1 = float(np.linalg.norm(vector1))
        length2 = float(np.linalg.norm(vector2))
        if length1 <= 1.0e-12 or length2 <= 1.0e-12:
            raise WaterReferenceError("degenerate angle bond")
        unit1, unit2 = vector1 / length1, vector2 / length2
        cosine = float(np.clip(np.dot(unit1, unit2), -1.0, 1.0))
        angle = math.acos(cosine)
        sine = math.sqrt(max(1.0e-24, 1.0 - cosine * cosine))
        angle_delta = angle - equilibrium_angle
        energy += 0.5 * angle_k * angle_delta * angle_delta
        derivative = angle_k * angle_delta
        force_h1 = derivative * (unit2 - cosine * unit1) / (length1 * sine)
        force_h2 = derivative * (unit1 - cosine * unit2) / (length2 * sine)
        forces[hydrogen1] += force_h1
        forces[hydrogen2] += force_h2
        forces[oxygen] -= force_h1 + force_h2

    sigma = np.array(
        [water["oxygen_sigma_angstrom"], water["hydrogen_sigma_angstrom"]],
        dtype=float,
    )
    epsilon = np.array(
        [
            water["oxygen_epsilon_kcal_per_mol"],
            water["hydrogen_epsilon_kcal_per_mol"],
        ],
        dtype=float,
    )
    coulomb = float(profile["coulomb_constant_kcal_a_per_mol_e2"])
    cutoff, switch_start, dielectric, screening_kappa, minimum_distance = (
        _nonbonded_settings(profile)
    )
    for first in range(len(positions)):
        if atom_types[first] not in (0, 1):
            raise WaterReferenceError("unsupported atom type")
        for second in range(first + 1, len(positions)):
            if first // 3 == second // 3:
                continue
            if atom_types[second] not in (0, 1):
                raise WaterReferenceError("unsupported atom type")
            displacement = minimum_image(positions[second] - positions[first], box)
            squared_distance = float(np.dot(displacement, displacement))
            distance = math.sqrt(squared_distance)
            if distance < minimum_distance:
                raise WaterReferenceError("overlapping atoms")
            if cutoff is not None and distance > cutoff:
                continue
            mixed_sigma = 0.5 * (
                sigma[atom_types[first]] + sigma[atom_types[second]]
            )
            mixed_epsilon = math.sqrt(
                epsilon[atom_types[first]] * epsilon[atom_types[second]]
            )
            lennard_jones = 0.0
            lennard_jones_derivative = 0.0
            if mixed_sigma > 0.0 and mixed_epsilon > 0.0:
                ratio6 = (mixed_sigma / distance) ** 6
                ratio12 = ratio6 * ratio6
                lennard_jones = 4.0 * mixed_epsilon * (ratio12 - ratio6)
                lennard_jones_derivative = (
                    24.0 * mixed_epsilon * (-2.0 * ratio12 + ratio6) / distance
                )
            screened_charge = (
                charges[first]
                * charges[second]
                * math.exp(-screening_kappa * distance)
            )
            electrostatic = coulomb * screened_charge / (dielectric * distance)
            electrostatic_derivative = electrostatic * (
                -screening_kappa - 1.0 / distance
            )
            switch, switch_derivative = _switching_value(
                distance, switch_start, cutoff
            )
            pair_energy = lennard_jones + electrostatic
            energy += pair_energy * switch
            energy_derivative = (
                (lennard_jones_derivative + electrostatic_derivative) * switch
                + pair_energy * switch_derivative
            )
            force_first = energy_derivative * displacement / distance
            forces[first] += force_first
            forces[second] -= force_first
    if not math.isfinite(energy) or not np.isfinite(forces).all():
        raise WaterReferenceError("nonfinite energy or force")
    return float(energy), forces


def step_verlet(
    profile: dict[str, Any],
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    charges: np.ndarray,
    atom_types: np.ndarray,
    box: float,
    timestep_fs: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    if not math.isfinite(timestep_fs) or timestep_fs <= 0.0:
        raise WaterReferenceError("timestep must be positive and finite")
    positions = np.asarray(positions, dtype=np.float64)
    velocities = np.asarray(velocities, dtype=np.float64)
    masses = np.asarray(masses, dtype=np.float64)
    if velocities.shape != positions.shape or len(masses) != len(positions):
        raise WaterReferenceError("dynamics input shape mismatch")
    if not np.isfinite(velocities).all() or not np.isfinite(masses).all():
        raise WaterReferenceError("nonfinite dynamics state")
    if np.any(masses <= 0.0):
        raise WaterReferenceError("masses must be positive")
    acceleration_factor = float(profile["force_to_acceleration"])
    _energy0, force0 = energy_forces(
        profile, positions, charges, atom_types, box
    )
    acceleration0 = acceleration_factor * force0 / masses[:, None]
    new_positions = (
        positions
        + velocities * timestep_fs
        + 0.5 * acceleration0 * timestep_fs * timestep_fs
    )
    energy1, force1 = energy_forces(
        profile, new_positions, charges, atom_types, box
    )
    acceleration1 = acceleration_factor * force1 / masses[:, None]
    new_velocities = velocities + 0.5 * (
        acceleration0 + acceleration1
    ) * timestep_fs
    return new_positions, new_velocities, energy1


def kinetic(
    masses: np.ndarray,
    velocities: np.ndarray,
    profile: dict[str, Any],
) -> float:
    return float(
        0.5
        * np.sum(masses[:, None] * velocities * velocities)
        / profile["force_to_acceleration"]
    )


def run_nve(
    profile: dict[str, Any],
    steps: int,
    timestep_fs: float,
) -> dict[str, Any]:
    if type(steps) is not int or steps < 0:
        raise WaterReferenceError("steps must be a non-negative integer")
    positions, masses, charges, atom_types, box = build_box(profile)
    velocities = np.zeros_like(positions)
    velocities[1, 2] = 1.0e-4
    velocities[2, 2] = -1.0e-4
    initial_potential, _ = energy_forces(
        profile, positions, charges, atom_types, box
    )
    initial_total = initial_potential + kinetic(masses, velocities, profile)
    for _ in range(steps):
        positions, velocities, _potential = step_verlet(
            profile,
            positions,
            velocities,
            masses,
            charges,
            atom_types,
            box,
            timestep_fs,
        )
    final_potential, _ = energy_forces(
        profile, positions, charges, atom_types, box
    )
    final_total = final_potential + kinetic(masses, velocities, profile)
    checkpoint = {
        "positions": positions.tolist(),
        "velocities": velocities.tolist(),
        "masses": masses.tolist(),
        "charges": charges.tolist(),
        "types": atom_types.tolist(),
        "box_angstrom": box,
        "absolute_step": steps,
    }
    checkpoint_sha256 = hashlib.sha256(
        json.dumps(
            checkpoint,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    return {
        "initial_total_energy": initial_total,
        "final_total_energy": final_total,
        "absolute_drift": final_total - initial_total,
        "checkpoint": checkpoint,
        "checkpoint_sha256": checkpoint_sha256,
        "authority": {
            "production_md_validated": False,
            "scientific_claim_authorized": False,
            "performance_claim_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--dt-fs", type=float, default=0.02)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output must be absent")
    try:
        result = run_nve(load_profile(args.profile), args.steps, args.dt_fs)
    except WaterReferenceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
