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

PROFILE_SCHEMA = "betelgeuze.engine_v2_water_box_reference_profile/1.0.0"


class WaterReferenceError(ValueError):
    pass


def load_profile(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_id") != PROFILE_SCHEMA:
        raise WaterReferenceError("water profile schema changed")
    authority = value.get("authority")
    if type(authority) is not dict or any(v is not False for v in authority.values()):
        raise WaterReferenceError("water authority escalated")
    return value


def water_geometry(profile: dict[str, Any]) -> np.ndarray:
    w = profile["water"]
    distance = float(w["oh_distance_angstrom"])
    half = math.radians(float(w["hoh_angle_degrees"])) / 2.0
    return np.array([
        [0.0, 0.0, 0.0],
        [distance * math.cos(half), distance * math.sin(half), 0.0],
        [distance * math.cos(half), -distance * math.sin(half), 0.0],
    ], dtype=np.float64)


def build_box(profile: dict[str, Any], count: int = 2, spacing: float = 4.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    if count < 1:
        raise WaterReferenceError("water count must be positive")
    geometry = water_geometry(profile)
    positions = np.vstack([geometry + np.array([i * spacing, 0.0, 0.0]) for i in range(count)])
    w = profile["water"]
    masses = np.tile([w["oxygen_mass_dalton"], w["hydrogen_mass_dalton"], w["hydrogen_mass_dalton"]], count).astype(float)
    charges = np.tile([w["oxygen_charge"], w["hydrogen_charge"], w["hydrogen_charge"]], count).astype(float)
    types = np.tile([0, 1, 1], count)
    box = max(12.0, count * spacing + 6.0)
    return positions, masses, charges, types, box


def minimum_image(delta: np.ndarray, box: float) -> np.ndarray:
    return delta - box * np.floor(delta / box + 0.5)


def energy_forces(profile: dict[str, Any], positions: np.ndarray, charges: np.ndarray, types: np.ndarray, box: float) -> tuple[float, np.ndarray]:
    positions = np.asarray(positions, dtype=np.float64)
    if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) % 3:
        raise WaterReferenceError("positions must contain complete waters")
    if not np.isfinite(positions).all() or box <= 0:
        raise WaterReferenceError("nonfinite state")
    forces = np.zeros_like(positions)
    energy = 0.0
    w = profile["water"]
    r0 = float(w["oh_distance_angstrom"])
    theta0 = math.radians(float(w["hoh_angle_degrees"]))
    kb = float(w["bond_k_kcal_per_mol_a2"])
    ka = float(w["angle_k_kcal_per_mol_rad2"])

    for base in range(0, len(positions), 3):
        o, h1, h2 = base, base + 1, base + 2
        for h in (h1, h2):
            d = positions[h] - positions[o]
            r = float(np.linalg.norm(d))
            if r <= 1e-12:
                raise WaterReferenceError("degenerate bond")
            dr = r - r0
            energy += 0.5 * kb * dr * dr
            f = kb * dr * d / r
            forces[o] += f
            forces[h] -= f

        u = positions[h1] - positions[o]
        v = positions[h2] - positions[o]
        ru, rv = float(np.linalg.norm(u)), float(np.linalg.norm(v))
        uhat, vhat = u / ru, v / rv
        cosine = float(np.clip(np.dot(uhat, vhat), -1.0, 1.0))
        theta = math.acos(cosine)
        sine = math.sqrt(max(1e-24, 1.0 - cosine * cosine))
        delta = theta - theta0
        energy += 0.5 * ka * delta * delta
        derivative = ka * delta
        fh1 = derivative * (vhat - cosine * uhat) / (ru * sine)
        fh2 = derivative * (uhat - cosine * vhat) / (rv * sine)
        forces[h1] += fh1
        forces[h2] += fh2
        forces[o] -= fh1 + fh2

    sigma = np.array([w["oxygen_sigma_angstrom"], w["hydrogen_sigma_angstrom"]], dtype=float)
    epsilon = np.array([w["oxygen_epsilon_kcal_per_mol"], w["hydrogen_epsilon_kcal_per_mol"]], dtype=float)
    coulomb = float(profile["coulomb_constant_kcal_a_per_mol_e2"])
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            if i // 3 == j // 3:
                continue
            d = minimum_image(positions[j] - positions[i], box)
            r2 = float(np.dot(d, d))
            if r2 <= 1e-20:
                raise WaterReferenceError("overlapping atoms")
            r = math.sqrt(r2)
            sig = 0.5 * (sigma[types[i]] + sigma[types[j]])
            eps = math.sqrt(epsilon[types[i]] * epsilon[types[j]])
            dedr = 0.0
            if sig > 0.0 and eps > 0.0:
                sr6 = (sig / r) ** 6
                sr12 = sr6 * sr6
                energy += 4.0 * eps * (sr12 - sr6)
                dedr += 24.0 * eps * (-2.0 * sr12 + sr6) / r
            energy += coulomb * charges[i] * charges[j] / r
            dedr += -coulomb * charges[i] * charges[j] / r2
            fi = dedr * d / r
            forces[i] += fi
            forces[j] -= fi
    return float(energy), forces


def step_verlet(profile: dict[str, Any], positions: np.ndarray, velocities: np.ndarray, masses: np.ndarray, charges: np.ndarray, types: np.ndarray, box: float, dt_fs: float) -> tuple[np.ndarray, np.ndarray, float]:
    factor = float(profile["force_to_acceleration"])
    energy0, force0 = energy_forces(profile, positions, charges, types, box)
    acceleration0 = factor * force0 / masses[:, None]
    new_positions = positions + velocities * dt_fs + 0.5 * acceleration0 * dt_fs * dt_fs
    energy1, force1 = energy_forces(profile, new_positions, charges, types, box)
    acceleration1 = factor * force1 / masses[:, None]
    new_velocities = velocities + 0.5 * (acceleration0 + acceleration1) * dt_fs
    return new_positions, new_velocities, energy1


def kinetic(masses: np.ndarray, velocities: np.ndarray, profile: dict[str, Any]) -> float:
    return float(0.5 * np.sum(masses[:, None] * velocities * velocities) / profile["force_to_acceleration"])


def run_nve(profile: dict[str, Any], steps: int, dt_fs: float) -> dict[str, Any]:
    positions, masses, charges, types, box = build_box(profile)
    velocities = np.zeros_like(positions)
    velocities[1, 2] = 1e-4
    velocities[2, 2] = -1e-4
    initial_potential, _ = energy_forces(profile, positions, charges, types, box)
    initial_total = initial_potential + kinetic(masses, velocities, profile)
    for _ in range(steps):
        positions, velocities, _potential = step_verlet(
            profile, positions, velocities, masses, charges, types, box, dt_fs
        )
    final_potential, _ = energy_forces(profile, positions, charges, types, box)
    final_total = final_potential + kinetic(masses, velocities, profile)
    checkpoint = {
        "positions": positions.tolist(), "velocities": velocities.tolist(),
        "masses": masses.tolist(), "charges": charges.tolist(),
        "types": types.tolist(), "box_angstrom": box, "absolute_step": steps,
    }
    checkpoint_sha = hashlib.sha256(
        json.dumps(checkpoint, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()
    return {
        "initial_total_energy": initial_total,
        "final_total_energy": final_total,
        "absolute_drift": final_total - initial_total,
        "checkpoint": checkpoint,
        "checkpoint_sha256": checkpoint_sha,
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
    result = run_nve(load_profile(args.profile), args.steps, args.dt_fs)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
