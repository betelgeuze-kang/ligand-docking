#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.definitions import ResearchConstants

try:
    import openmm as mm
    import openmm.unit as unit
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "openmm is required for this script. Install with: python3 -m pip install --user openmm"
    ) from exc


def _slug_target(name: str) -> str:
    out: List[str] = []
    prev_us = False
    for ch in str(name).lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    slug = "".join(out).strip("_")
    return slug or "target"


def _parse_targets(spec: str) -> List[str]:
    if str(spec).strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in str(spec).split(",") if x.strip()]


def _normalize_representation(raw: str) -> str:
    s = str(raw).strip().lower()
    if s in ("ca", "ca_only", "ca_bead"):
        return "ca"
    if s in ("ca_sc_2bead", "ca_sc", "2bead", "two_bead", "ca_sc_explicit"):
        return "ca_sc_2bead"
    raise ValueError(f"unsupported representation: {raw}")


def _load_ca_coords_from_pdb(path: str) -> np.ndarray:
    coords: List[List[float]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            atom_name = line[12:16].strip()
            if atom_name != "CA":
                continue
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            coords.append([x, y, z])
    if len(coords) == 0:
        raise ValueError(f"No CA atoms found in PDB: {path}")
    return np.asarray(coords, dtype=np.float32)


def _safe_angle(v1: np.ndarray, v2: np.ndarray) -> float:
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 < 1e-8 or n2 < 1e-8:
        return float(math.pi)
    c = float(np.dot(v1, v2) / (n1 * n2))
    c = max(-1.0, min(1.0, c))
    return float(math.acos(c))


def _safe_normalize(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    if n < 1e-12:
        return np.zeros_like(vec)
    return vec / n


def _compute_virtual_sc_coords(coords_ca_nm: np.ndarray, sc_distance_nm: float) -> np.ndarray:
    n = int(coords_ca_nm.shape[0])
    if n == 0:
        return np.zeros((0, 3), dtype=np.float64)
    if n == 1:
        return np.asarray(coords_ca_nm + np.array([[0.0, float(sc_distance_nm), 0.0]], dtype=np.float64))

    out = np.zeros((n, 3), dtype=np.float64)
    ref_a = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    ref_b = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    ref_c = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    for i in range(n):
        if i == 0:
            tangent = coords_ca_nm[1] - coords_ca_nm[0]
        elif i == (n - 1):
            tangent = coords_ca_nm[n - 1] - coords_ca_nm[n - 2]
        else:
            tangent = coords_ca_nm[i + 1] - coords_ca_nm[i - 1]
        t_hat = _safe_normalize(tangent)
        if float(np.linalg.norm(t_hat)) < 1e-8:
            t_hat = ref_c

        ref = ref_a if abs(float(np.dot(t_hat, ref_a))) < 0.90 else ref_b
        normal = np.cross(t_hat, ref)
        n_hat = _safe_normalize(normal)
        if float(np.linalg.norm(n_hat)) < 1e-8:
            n_hat = ref_b
        side = np.cross(n_hat, t_hat)
        s_hat = _safe_normalize(side)
        if float(np.linalg.norm(s_hat)) < 1e-8:
            s_hat = ref_b
        out[i] = coords_ca_nm[i] + float(sc_distance_nm) * s_hat
    return out


def _build_ca_system(
    coords_nm: np.ndarray,
    sigma_nm: float,
    epsilon_kj: float,
    bond_k_kj_nm2: float,
    angle_k_kj_rad2: float,
    cutoff_nm: float,
    mass_amu: float,
) -> mm.System:
    n = int(coords_nm.shape[0])
    system = mm.System()
    mass = float(mass_amu) * unit.amu
    for _ in range(n):
        system.addParticle(mass)

    bond = mm.HarmonicBondForce()
    for i in range(n - 1):
        r0 = float(np.linalg.norm(coords_nm[i + 1] - coords_nm[i]))
        bond.addBond(
            i,
            i + 1,
            r0 * unit.nanometer,
            float(bond_k_kj_nm2) * unit.kilojoule_per_mole / (unit.nanometer**2),
        )
    system.addForce(bond)

    angle = mm.HarmonicAngleForce()
    for i in range(n - 2):
        theta0 = _safe_angle(coords_nm[i] - coords_nm[i + 1], coords_nm[i + 2] - coords_nm[i + 1])
        angle.addAngle(
            i,
            i + 1,
            i + 2,
            theta0 * unit.radian,
            float(angle_k_kj_rad2) * unit.kilojoule_per_mole / (unit.radian**2),
        )
    system.addForce(angle)

    nb = mm.NonbondedForce()
    nb.setNonbondedMethod(mm.NonbondedForce.CutoffNonPeriodic)
    nb.setCutoffDistance(float(cutoff_nm) * unit.nanometer)
    for _ in range(n):
        nb.addParticle(
            0.0 * unit.elementary_charge,
            float(sigma_nm) * unit.nanometer,
            float(epsilon_kj) * unit.kilojoule_per_mole,
        )
    for i in range(n - 1):
        # Exclude directly bonded neighbors from LJ.
        nb.addException(
            i,
            i + 1,
            0.0 * unit.elementary_charge**2,
            0.1 * unit.nanometer,
            0.0 * unit.kilojoule_per_mole,
        )
    system.addForce(nb)
    return system


def _build_ca_sc_system(
    coords_ca_nm: np.ndarray,
    coords_sc_nm: np.ndarray,
    sigma_nm: float,
    epsilon_kj: float,
    bond_k_kj_nm2: float,
    angle_k_kj_rad2: float,
    sidechain_bond_k_kj_nm2: float,
    sidechain_angle_k_kj_rad2: float,
    cutoff_nm: float,
    ca_mass_amu: float,
    sc_mass_amu: float,
    sc_sigma_scale: float,
    sc_epsilon_scale: float,
    exclude_local_sc_neighbors: bool,
) -> mm.System:
    n = int(coords_ca_nm.shape[0])
    if int(coords_sc_nm.shape[0]) != n:
        raise ValueError(f"ca/sc length mismatch: ca={coords_ca_nm.shape[0]} sc={coords_sc_nm.shape[0]}")
    system = mm.System()
    for _ in range(n):
        system.addParticle(float(ca_mass_amu) * unit.amu)
    for _ in range(n):
        system.addParticle(float(sc_mass_amu) * unit.amu)

    bond = mm.HarmonicBondForce()
    for i in range(n - 1):
        r0 = float(np.linalg.norm(coords_ca_nm[i + 1] - coords_ca_nm[i]))
        bond.addBond(
            i,
            i + 1,
            r0 * unit.nanometer,
            float(bond_k_kj_nm2) * unit.kilojoule_per_mole / (unit.nanometer**2),
        )
    for i in range(n):
        sc_idx = n + i
        r0_sc = float(np.linalg.norm(coords_sc_nm[i] - coords_ca_nm[i]))
        bond.addBond(
            i,
            sc_idx,
            r0_sc * unit.nanometer,
            float(sidechain_bond_k_kj_nm2) * unit.kilojoule_per_mole / (unit.nanometer**2),
        )
    system.addForce(bond)

    angle = mm.HarmonicAngleForce()
    for i in range(n - 2):
        theta0 = _safe_angle(
            coords_ca_nm[i] - coords_ca_nm[i + 1],
            coords_ca_nm[i + 2] - coords_ca_nm[i + 1],
        )
        angle.addAngle(
            i,
            i + 1,
            i + 2,
            theta0 * unit.radian,
            float(angle_k_kj_rad2) * unit.kilojoule_per_mole / (unit.radian**2),
        )
    for i in range(n - 1):
        sc_i = n + i
        theta_left = _safe_angle(
            coords_sc_nm[i] - coords_ca_nm[i],
            coords_ca_nm[i + 1] - coords_ca_nm[i],
        )
        angle.addAngle(
            sc_i,
            i,
            i + 1,
            theta_left * unit.radian,
            float(sidechain_angle_k_kj_rad2) * unit.kilojoule_per_mole / (unit.radian**2),
        )
        sc_ip1 = n + i + 1
        theta_right = _safe_angle(
            coords_ca_nm[i] - coords_ca_nm[i + 1],
            coords_sc_nm[i + 1] - coords_ca_nm[i + 1],
        )
        angle.addAngle(
            i,
            i + 1,
            sc_ip1,
            theta_right * unit.radian,
            float(sidechain_angle_k_kj_rad2) * unit.kilojoule_per_mole / (unit.radian**2),
        )
    system.addForce(angle)

    nb = mm.NonbondedForce()
    nb.setNonbondedMethod(mm.NonbondedForce.CutoffNonPeriodic)
    nb.setCutoffDistance(float(cutoff_nm) * unit.nanometer)

    sigma_ca = float(sigma_nm)
    sigma_sc = float(sigma_nm) * float(sc_sigma_scale)
    eps_ca = float(epsilon_kj)
    eps_sc = float(epsilon_kj) * float(sc_epsilon_scale)
    for _ in range(n):
        nb.addParticle(
            0.0 * unit.elementary_charge,
            sigma_ca * unit.nanometer,
            eps_ca * unit.kilojoule_per_mole,
        )
    for _ in range(n):
        nb.addParticle(
            0.0 * unit.elementary_charge,
            sigma_sc * unit.nanometer,
            eps_sc * unit.kilojoule_per_mole,
        )

    excluded_pairs: set[Tuple[int, int]] = set()
    for i in range(n - 1):
        excluded_pairs.add((i, i + 1))
    for i in range(n):
        excluded_pairs.add((i, n + i))
    if bool(exclude_local_sc_neighbors):
        for i in range(n - 1):
            excluded_pairs.add((i, n + i + 1))
            excluded_pairs.add((i + 1, n + i))

    for i, j in sorted(excluded_pairs):
        nb.addException(
            int(i),
            int(j),
            0.0 * unit.elementary_charge**2,
            0.1 * unit.nanometer,
            0.0 * unit.kilojoule_per_mole,
        )
    system.addForce(nb)
    return system


def _choose_platform(name: str) -> mm.Platform:
    want = str(name).strip()
    if want:
        return mm.Platform.getPlatformByName(want)
    for cand in ("CUDA", "OpenCL", "CPU", "Reference"):
        try:
            return mm.Platform.getPlatformByName(cand)
        except Exception:
            continue
    raise RuntimeError("No usable OpenMM platform found.")


def _simulate_target(
    target: str,
    pdb_path: str,
    out_npy: str,
    out_ca_projection_npy: Optional[str],
    steps: int,
    save_stride: int,
    temperature_k: float,
    friction_ps: float,
    dt_ps: float,
    sigma_nm: float,
    epsilon_kj: float,
    bond_k_kj_nm2: float,
    angle_k_kj_rad2: float,
    cutoff_nm: float,
    platform_name: str,
    seed: int,
    minimize_iters: int,
    representation: str,
    sc_distance_nm: float,
    ca_mass_amu: float,
    sc_mass_amu: float,
    sc_sigma_scale: float,
    sc_epsilon_scale: float,
    sidechain_bond_k_kj_nm2: float,
    sidechain_angle_k_kj_rad2: float,
    exclude_local_sc_neighbors: bool,
    save_ca_projection: bool,
) -> Dict[str, Any]:
    coords_a = _load_ca_coords_from_pdb(pdb_path)
    coords_ca_nm = np.asarray(coords_a * 0.1, dtype=np.float64)
    rep_i = _normalize_representation(representation)
    n_res = int(coords_ca_nm.shape[0])

    if target in ResearchConstants.CHALLENGES:
        expected_n = int(ResearchConstants.CHALLENGES[target]["n_res"])
        if int(coords_ca_nm.shape[0]) != expected_n:
            raise ValueError(
                f"n_res mismatch for {target}: pdb={coords_ca_nm.shape[0]} expected={expected_n}"
            )

    bead_order = "ca_only"
    notes = "REAL_MD_OPENMM_CA_BEAD"
    if rep_i == "ca_sc_2bead":
        coords_sc_nm = _compute_virtual_sc_coords(coords_ca_nm, sc_distance_nm=float(sc_distance_nm))
        coords_nm = np.concatenate([coords_ca_nm, coords_sc_nm], axis=0)
        system = _build_ca_sc_system(
            coords_ca_nm=coords_ca_nm,
            coords_sc_nm=coords_sc_nm,
            sigma_nm=float(sigma_nm),
            epsilon_kj=float(epsilon_kj),
            bond_k_kj_nm2=float(bond_k_kj_nm2),
            angle_k_kj_rad2=float(angle_k_kj_rad2),
            sidechain_bond_k_kj_nm2=float(sidechain_bond_k_kj_nm2),
            sidechain_angle_k_kj_rad2=float(sidechain_angle_k_kj_rad2),
            cutoff_nm=float(cutoff_nm),
            ca_mass_amu=float(ca_mass_amu),
            sc_mass_amu=float(sc_mass_amu),
            sc_sigma_scale=float(sc_sigma_scale),
            sc_epsilon_scale=float(sc_epsilon_scale),
            exclude_local_sc_neighbors=bool(exclude_local_sc_neighbors),
        )
        bead_order = "ca_then_sc"
        notes = "REAL_MD_OPENMM_CA_SC_2BEAD"
    else:
        coords_nm = coords_ca_nm
        system = _build_ca_system(
            coords_nm=coords_nm,
            sigma_nm=float(sigma_nm),
            epsilon_kj=float(epsilon_kj),
            bond_k_kj_nm2=float(bond_k_kj_nm2),
            angle_k_kj_rad2=float(angle_k_kj_rad2),
            cutoff_nm=float(cutoff_nm),
            mass_amu=float(ca_mass_amu),
        )

    integ = mm.LangevinMiddleIntegrator(
        float(temperature_k) * unit.kelvin,
        float(friction_ps) / unit.picosecond,
        float(dt_ps) * unit.picoseconds,
    )
    integ.setRandomNumberSeed(int(seed))

    platform = _choose_platform(platform_name)
    ctx = mm.Context(system, integ, platform)
    ctx.setPositions(coords_nm * unit.nanometer)
    mm.LocalEnergyMinimizer.minimize(ctx, 10.0, int(minimize_iters))

    stride = max(1, int(save_stride))
    total_steps = max(1, int(steps))
    frames: List[np.ndarray] = []

    state0 = ctx.getState(getPositions=True)
    p0 = state0.getPositions(asNumpy=True).value_in_unit(unit.angstrom)
    frames.append(np.asarray(p0, dtype=np.float32))

    done = 0
    while done < total_steps:
        step_now = min(stride, total_steps - done)
        integ.step(int(step_now))
        done += int(step_now)
        st = ctx.getState(getPositions=True)
        pa = st.getPositions(asNumpy=True).value_in_unit(unit.angstrom)
        frames.append(np.asarray(pa, dtype=np.float32))

    traj = np.stack(frames, axis=0)  # [T, N_atoms, 3], Angstrom
    os.makedirs(os.path.dirname(out_npy) or ".", exist_ok=True)
    np.save(out_npy, traj)
    ca_projection_path = ""
    if rep_i == "ca_sc_2bead" and bool(save_ca_projection) and out_ca_projection_npy:
        traj_ca = traj[:, :n_res, :]
        os.makedirs(os.path.dirname(out_ca_projection_npy) or ".", exist_ok=True)
        np.save(out_ca_projection_npy, traj_ca)
        ca_projection_path = os.path.abspath(out_ca_projection_npy)

    e_state = ctx.getState(getEnergy=True)
    potential_kj = float(e_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))
    final = traj[-1, :n_res, :] if rep_i == "ca_sc_2bead" else traj[-1]
    com = final.mean(axis=0, keepdims=True)
    rg = float(np.sqrt(np.mean(np.sum((final - com) ** 2, axis=1))))

    label_suffix = "openmm_ca_sc_2bead_md" if rep_i == "ca_sc_2bead" else "openmm_ca_md"
    n_atoms = int(traj.shape[1])
    beads_per_residue = float(n_atoms) / max(float(n_res), 1.0)
    return {
        "target": target,
        "path": os.path.abspath(out_npy),
        "engine": "openmm",
        "label": f"{target}_{label_suffix}",
        "frame": -1,
        "key": "",
        "source_engine": "openmm",
        "source_path": os.path.abspath(out_npy),
        "source_label": f"{target}_{label_suffix}",
        "notes": notes,
        "representation": rep_i,
        "bead_order": bead_order,
        "n_res": int(n_res),
        "n_atoms": int(n_atoms),
        "beads_per_residue": float(beads_per_residue),
        "ca_projection_path": ca_projection_path,
        "frames": int(traj.shape[0]),
        "steps": int(total_steps),
        "save_stride": int(stride),
        "temperature_k": float(temperature_k),
        "friction_ps": float(friction_ps),
        "dt_ps": float(dt_ps),
        "sigma_nm": float(sigma_nm),
        "epsilon_kj_mol": float(epsilon_kj),
        "bond_k_kj_nm2": float(bond_k_kj_nm2),
        "angle_k_kj_rad2": float(angle_k_kj_rad2),
        "sidechain_bond_k_kj_nm2": float(sidechain_bond_k_kj_nm2),
        "sidechain_angle_k_kj_rad2": float(sidechain_angle_k_kj_rad2),
        "sc_distance_nm": float(sc_distance_nm),
        "ca_mass_amu": float(ca_mass_amu),
        "sc_mass_amu": float(sc_mass_amu),
        "sc_sigma_scale": float(sc_sigma_scale),
        "sc_epsilon_scale": float(sc_epsilon_scale),
        "exclude_local_sc_neighbors": bool(exclude_local_sc_neighbors),
        "cutoff_nm": float(cutoff_nm),
        "platform": platform.getName(),
        "seed": int(seed),
        "final_potential_kj_mol": potential_kj,
        "final_rg_A": rg,
    }


def generate_openmm_ca_md_references(args: argparse.Namespace) -> Dict[str, Any]:
    targets = _parse_targets(str(args.targets))
    out_dir = os.path.abspath(str(args.out_dir))
    os.makedirs(out_dir, exist_ok=True)
    representation = _normalize_representation(getattr(args, "representation", "ca_sc_2bead"))

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for idx, target in enumerate(targets):
        slug = _slug_target(target)
        pdb_path = os.path.join("data", "native", f"{slug}.pdb")
        if not os.path.exists(pdb_path):
            raise FileNotFoundError(f"native pdb not found for {target}: {pdb_path}")
        rep_tag = "ca_sc_2bead" if representation == "ca_sc_2bead" else "ca"
        out_npy = os.path.join(out_dir, f"{slug}_openmm_{rep_tag}_md.npy")
        out_ca_projection_npy = None
        if representation == "ca_sc_2bead" and bool(args.save_ca_projection):
            out_ca_projection_npy = os.path.join(out_dir, f"{slug}_openmm_{rep_tag}_md_ca.npy")
        row = _simulate_target(
            target=target,
            pdb_path=pdb_path,
            out_npy=out_npy,
            out_ca_projection_npy=out_ca_projection_npy,
            steps=int(args.steps),
            save_stride=int(args.save_stride),
            temperature_k=float(args.temperature_k),
            friction_ps=float(args.friction_ps),
            dt_ps=float(args.dt_ps),
            sigma_nm=float(args.sigma_nm),
            epsilon_kj=float(args.epsilon_kj),
            bond_k_kj_nm2=float(args.bond_k_kj_nm2),
            angle_k_kj_rad2=float(args.angle_k_kj_rad2),
            cutoff_nm=float(args.cutoff_nm),
            platform_name=str(args.platform),
            seed=int(args.seed_base) + idx,
            minimize_iters=int(args.minimize_iters),
            representation=representation,
            sc_distance_nm=float(args.sc_distance_nm),
            ca_mass_amu=float(args.ca_mass_amu),
            sc_mass_amu=float(args.sc_mass_amu),
            sc_sigma_scale=float(args.sc_sigma_scale),
            sc_epsilon_scale=float(args.sc_epsilon_scale),
            sidechain_bond_k_kj_nm2=float(args.sidechain_bond_k_kj_nm2),
            sidechain_angle_k_kj_rad2=float(args.sidechain_angle_k_kj_rad2),
            exclude_local_sc_neighbors=bool(args.exclude_local_sc_neighbors),
            save_ca_projection=bool(args.save_ca_projection),
        )
        rows.append(row)
        print(
            f"[{idx+1}/{len(targets)}] {target} -> {row['path']} "
            f"(repr={row['representation']}, platform={row['platform']}, Rg={row['final_rg_A']:.3f} A)"
        )

    manifest_cols = [
        "target",
        "path",
        "engine",
        "label",
        "frame",
        "key",
        "source_engine",
        "source_path",
        "source_label",
        "notes",
        "representation",
        "bead_order",
        "n_res",
        "n_atoms",
        "beads_per_residue",
        "ca_projection_path",
        "temperature_k",
        "friction_ps",
        "dt_ps",
        "steps",
        "save_stride",
        "sigma_nm",
        "epsilon_kj_mol",
        "bond_k_kj_nm2",
        "angle_k_kj_rad2",
        "sidechain_bond_k_kj_nm2",
        "sidechain_angle_k_kj_rad2",
        "sc_distance_nm",
        "ca_mass_amu",
        "sc_mass_amu",
        "sc_sigma_scale",
        "sc_epsilon_scale",
        "exclude_local_sc_neighbors",
        "cutoff_nm",
        "platform",
        "seed",
    ]
    os.makedirs(os.path.dirname(str(args.out_manifest)) or ".", exist_ok=True)
    with open(str(args.out_manifest), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest_cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in manifest_cols})

    summary = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "targets": targets,
        "target_count": int(len(rows)),
        "out_dir": out_dir,
        "out_manifest": os.path.abspath(str(args.out_manifest)),
        "elapsed_sec": float(time.time() - t0),
        "representation": representation,
        "steps": int(args.steps),
        "save_stride": int(args.save_stride),
        "temperature_k": float(args.temperature_k),
        "friction_ps": float(args.friction_ps),
        "dt_ps": float(args.dt_ps),
        "sigma_nm": float(args.sigma_nm),
        "epsilon_kj_mol": float(args.epsilon_kj),
        "bond_k_kj_nm2": float(args.bond_k_kj_nm2),
        "angle_k_kj_rad2": float(args.angle_k_kj_rad2),
        "cutoff_nm": float(args.cutoff_nm),
    }
    os.makedirs(os.path.dirname(str(args.out_json)) or ".", exist_ok=True)
    with open(str(args.out_json), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)

    return {"summary": summary, "rows": rows}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate OpenMM coarse-grained MD coordinate references (CA or CA-SC explicit 2-bead)."
    )
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--out-dir", type=str, default="runs/real_md_openmm_2026-02-15")
    parser.add_argument("--out-manifest", type=str, default="runs/real_md_source_manifest_openmm_2026-02-15.csv")
    parser.add_argument("--out-json", type=str, default="runs/real_md_source_manifest_openmm_2026-02-15_summary.json")
    parser.add_argument(
        "--representation",
        type=str,
        default="ca_sc_2bead",
        choices=["ca", "ca_sc_2bead"],
        help="Reference representation: CA-only or explicit CA+SC 2-bead (2N atoms).",
    )
    parser.add_argument("--steps", type=int, default=20000)
    parser.add_argument("--save-stride", type=int, default=200)
    parser.add_argument("--temperature-k", type=float, default=300.0)
    parser.add_argument("--friction-ps", type=float, default=1.0)
    parser.add_argument("--dt-ps", type=float, default=0.004)
    parser.add_argument("--sigma-nm", type=float, default=0.38)
    parser.add_argument("--epsilon-kj", type=float, default=0.50)
    parser.add_argument("--bond-k-kj-nm2", type=float, default=2500.0)
    parser.add_argument("--angle-k-kj-rad2", type=float, default=40.0)
    parser.add_argument("--sidechain-bond-k-kj-nm2", type=float, default=2500.0)
    parser.add_argument("--sidechain-angle-k-kj-rad2", type=float, default=35.0)
    parser.add_argument("--sc-distance-nm", type=float, default=0.15)
    parser.add_argument("--ca-mass-amu", type=float, default=100.0)
    parser.add_argument("--sc-mass-amu", type=float, default=45.0)
    parser.add_argument("--sc-sigma-scale", type=float, default=0.95)
    parser.add_argument("--sc-epsilon-scale", type=float, default=0.90)
    parser.add_argument(
        "--exclude-local-sc-neighbors",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude CA(i)-SC(i+1)/CA(i+1)-SC(i) local pairs from LJ.",
    )
    parser.add_argument(
        "--save-ca-projection",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When using CA-SC 2-bead, also save CA-only projected trajectory [T,N,3].",
    )
    parser.add_argument("--cutoff-nm", type=float, default=1.2)
    parser.add_argument("--platform", type=str, default="", help="OpenMM platform name (auto if empty)")
    parser.add_argument("--seed-base", type=int, default=1234)
    parser.add_argument("--minimize-iters", type=int, default=200)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = generate_openmm_ca_md_references(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote manifest: {args.out_manifest}")
    print(f"Wrote summary: {args.out_json}")


if __name__ == "__main__":
    main()
