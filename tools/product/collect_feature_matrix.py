#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch

from core.config import config
from core.definitions import ResearchConstants
from core.forcefield import ForceField
from core.topology import TopologyFactory
from betelgeuze_engine.physics.neighbor import (
    CellListNeighborProvider,
    NeighborProviderConfig,
)
from run_validation import calculate_proxy_energy, calculate_rg, calculate_sasa_proxy
from theory.branches.hydrophobic_logic import HydrophobicLogic
from tools.pdb_loader import load_native_structure

DEFAULT_CONTACT_DIAGNOSTIC_MAX_NEIGHBORS = 256


def _slug(text: str) -> str:
    token = str(text).strip().lower()
    token = re.sub(r"[^a-z0-9]+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "target"


def _write_internal_postprocessed_pdb(
    out_path: str,
    coords: np.ndarray,
    *,
    target: str,
    sample_idx: int,
    step: int,
) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    n = int(coords.shape[0]) if isinstance(coords, np.ndarray) and coords.ndim == 2 else 0
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("REMARK GENERATED_BY collect_feature_matrix.py\n")
        f.write("REMARK SOURCE internal_postprocessed\n")
        f.write(f"REMARK TARGET {target}\n")
        f.write(f"REMARK SAMPLE_IDX {int(sample_idx)}\n")
        f.write(f"REMARK STEP {int(step)}\n")
        f.write("REMARK MODEL coarse_ca_projection\n")
        for i in range(n):
            x, y, z = coords[i].tolist()
            atom_id = int(i + 1)
            res_id = int(i + 1)
            line = (
                f"ATOM  {atom_id:5d}  CA  GLY A{res_id:4d}    "
                f"{float(x):8.3f}{float(y):8.3f}{float(z):8.3f}"
                "  1.00  0.00           C\n"
            )
            f.write(line)
        for i in range(1, n):
            f.write(f"CONECT{i:5d}{(i + 1):5d}\n")
        if n >= 2:
            f.write(f"TER   {int(n + 1):5d}      GLY A{int(n):4d}\n")
        f.write("END\n")


def _normalize_box_vec(box_like: Any) -> np.ndarray:
    arr = np.asarray(box_like, dtype=np.float32).reshape(-1)
    if arr.size <= 0:
        arr = np.asarray([100.0, 100.0, 100.0], dtype=np.float32)
    elif arr.size == 1:
        arr = np.repeat(arr, 3).astype(np.float32, copy=False)
    else:
        arr = arr[:3].astype(np.float32, copy=False)
    arr = np.where(arr > 1e-6, arr, 100.0).astype(np.float32, copy=False)
    return arr


def _unwrap_polymer_coords(coords_wrapped: np.ndarray, box_vec: np.ndarray) -> np.ndarray:
    c = np.asarray(coords_wrapped, dtype=np.float32)
    if c.ndim != 2 or c.shape[0] <= 1 or c.shape[1] != 3:
        return c
    b = _normalize_box_vec(box_vec)
    out = np.zeros_like(c, dtype=np.float32)
    out[0] = c[0]
    prev_wrapped = c[0]
    for i in range(1, c.shape[0]):
        cur = c[i]
        delta = cur - prev_wrapped
        delta = delta - np.round(delta / b) * b
        out[i] = out[i - 1] + delta
        prev_wrapped = cur
    # Center for stable viewer framing.
    out = out - np.mean(out, axis=0, keepdims=True)
    return out


def _parse_targets(spec: str) -> List[str]:
    if spec.strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in spec.split(",") if x.strip()]


def _load_native(target: str, n_res: int) -> torch.Tensor:
    native_coords, _ = load_native_structure(target)
    if native_coords is None:
        native_coords = (
            torch.linspace(0, n_res - 1, n_res, device=config.DEVICE)
            .view(n_res, 1)
            .repeat(1, 3)
        )
    return native_coords.to(config.DEVICE, dtype=torch.float32)


def _rmsd(coords: torch.Tensor, native: torch.Tensor) -> float:
    diff = coords - native
    return float(torch.sqrt(torch.mean(torch.sum(diff * diff, dim=-1))).item())


def _contact_graph_stats(
    coords: torch.Tensor,
    cutoff: float,
    *,
    max_neighbors: int = DEFAULT_CONTACT_DIAGNOSTIC_MAX_NEIGHBORS,
) -> Tuple[int, int]:
    n = int(coords.shape[0])
    if n <= 1:
        return 0, n
    pairs = CellListNeighborProvider(
        NeighborProviderConfig(
            cutoff=float(cutoff),
            max_neighbor_count=int(max_neighbors),
            max_atoms_per_cell=max(8, int(max_neighbors)),
        )
    ).build(coords.reshape(1, n, 3))
    diagnostics = dict(pairs.diagnostics)
    if diagnostics.get("overflow") is True:
        raise ValueError(
            "feature_matrix_contact_graph neighbor provider overflow; "
            f"max_observed_neighbors={diagnostics.get('max_observed_neighbors')}"
        )

    idx_cpu = pairs.idx[0].detach().cpu()
    mask_cpu = pairs.mask[0].detach().cpu()
    adjacency: list[set[int]] = [set() for _ in range(n)]
    edges: set[tuple[int, int]] = set()
    for i in range(n):
        for j in idx_cpu[i][mask_cpu[i]].tolist():
            j = int(j)
            if i == j:
                continue
            a, b = (i, j) if i < j else (j, i)
            edges.add((a, b))
            adjacency[i].add(j)
            adjacency[j].add(i)

    visited = [False] * n
    max_size = 0
    for start in range(n):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        size = 0
        while stack:
            atom_idx = stack.pop()
            size += 1
            for neighbor_idx in adjacency[atom_idx]:
                if not visited[neighbor_idx]:
                    visited[neighbor_idx] = True
                    stack.append(neighbor_idx)
        max_size = max(max_size, size)
    return len(edges), int(max_size)


def _contact_adjacency(
    coords: torch.Tensor,
    cutoff: float,
    *,
    max_dense_atoms: int = DEFAULT_CONTACT_DIAGNOSTIC_MAX_NEIGHBORS,
) -> torch.Tensor:
    n = int(coords.shape[0])
    edges, _cluster = _contact_graph_stats(
        coords,
        cutoff=cutoff,
        max_neighbors=max_dense_atoms,
    )
    adj = torch.zeros((n, n), dtype=torch.bool, device=coords.device)
    if edges == 0:
        return adj
    pairs = CellListNeighborProvider(
        NeighborProviderConfig(
            cutoff=float(cutoff),
            max_neighbor_count=int(max_dense_atoms),
            max_atoms_per_cell=max(8, int(max_dense_atoms)),
        )
    ).build(coords.reshape(1, n, 3))
    idx_cpu = pairs.idx[0].detach().cpu()
    mask_cpu = pairs.mask[0].detach().cpu()
    for i in range(n):
        for j in idx_cpu[i][mask_cpu[i]].tolist():
            if i != int(j):
                adj[i, int(j)] = True
    return adj


def _largest_component_size(adj: torch.Tensor) -> int:
    n = int(adj.shape[0])
    if n == 0:
        return 0
    visited = [False] * n
    max_size = 0
    for start in range(n):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        size = 0
        while stack:
            u = stack.pop()
            size += 1
            neigh = torch.nonzero(adj[u], as_tuple=False).view(-1).tolist()
            for v in neigh:
                if not visited[v]:
                    visited[v] = True
                    stack.append(v)
        if size > max_size:
            max_size = size
    return int(max_size)


def _compactness_and_cluster(
    coords: torch.Tensor,
    cutoff: float,
    *,
    max_dense_atoms: int = DEFAULT_CONTACT_DIAGNOSTIC_MAX_NEIGHBORS,
    max_neighbors: int | None = None,
) -> Tuple[float, int]:
    n = int(coords.shape[0])
    if n <= 1:
        return 0.0, n
    edge_count, cluster_max = _contact_graph_stats(
        coords,
        cutoff=cutoff,
        max_neighbors=int(max_neighbors if max_neighbors is not None else max_dense_atoms),
    )
    edges = float(edge_count)
    denom = float(n * (n - 1) / 2.0)
    compactness = float(edges / max(denom, 1.0))
    return compactness, cluster_max


def _bond_angles(coords: torch.Tensor) -> torch.Tensor:
    n = int(coords.shape[0])
    out = torch.full((n,), float("nan"), dtype=torch.float32, device=coords.device)
    if n < 3:
        return out
    v1 = coords[:-2] - coords[1:-1]
    v2 = coords[2:] - coords[1:-1]
    n1 = torch.norm(v1, dim=-1).clamp_min(1e-8)
    n2 = torch.norm(v2, dim=-1).clamp_min(1e-8)
    cosang = torch.sum(v1 * v2, dim=-1) / (n1 * n2)
    theta = torch.acos(torch.clamp(cosang, -1.0, 1.0))
    out[1:-1] = theta
    return out


def _dihedral_angles(coords: torch.Tensor) -> torch.Tensor:
    n = int(coords.shape[0])
    out = torch.full((n,), float("nan"), dtype=torch.float32, device=coords.device)
    if n < 4:
        return out
    p0 = coords[:-3]
    p1 = coords[1:-2]
    p2 = coords[2:-1]
    p3 = coords[3:]

    b0 = p1 - p0
    b1 = p2 - p1
    b2 = p3 - p2

    b1n = b1 / torch.norm(b1, dim=-1, keepdim=True).clamp_min(1e-8)
    v = b0 - torch.sum(b0 * b1n, dim=-1, keepdim=True) * b1n
    w = b2 - torch.sum(b2 * b1n, dim=-1, keepdim=True) * b1n

    x = torch.sum(v * w, dim=-1)
    y = torch.sum(torch.cross(b1n, v, dim=-1) * w, dim=-1)
    phi = torch.atan2(y, x)
    out[1:-2] = phi
    return out


def _nanvar_k(series_2d: np.ndarray, kbt: float) -> np.ndarray:
    # series_2d: [n_frames, n_res]
    if series_2d.size == 0:
        return np.array([], dtype=np.float32)
    n_res = int(series_2d.shape[1])
    out = np.full((n_res,), np.nan, dtype=np.float32)
    for r in range(n_res):
        vals = series_2d[:, r]
        vals = vals[np.isfinite(vals)]
        if vals.size < 2:
            continue
        var = float(np.var(vals))
        if var > 1e-8:
            out[r] = float(kbt / var)
    return out


def _float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    try:
        fv = float(v)
    except Exception:
        return None
    if not math.isfinite(fv):
        return None
    return fv


def _stable_int_key(text: str) -> int:
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _parse_float_grid(spec: str, default_value: float) -> List[float]:
    raw = [x.strip() for x in str(spec).replace("|", ",").split(",") if x.strip()]
    vals: List[float] = []
    for tok in raw:
        try:
            vals.append(float(tok))
        except Exception:
            continue
    if not vals:
        vals = [float(default_value)]
    return vals


def _parse_int_grid(spec: str, default_value: int) -> List[int]:
    raw = [x.strip() for x in str(spec).replace("|", ",").split(",") if x.strip()]
    vals: List[int] = []
    for tok in raw:
        try:
            vals.append(int(float(tok)))
        except Exception:
            continue
    if not vals:
        vals = [int(default_value)]
    return vals


def _make_forcefield(
    target: str,
    n_res: int,
    t_conf: Dict[str, Any],
    force_backend: str,
    neighbor_settings: Dict[str, Any],
    ff_params: Dict[str, Any],
) -> ForceField:
    top = TopologyFactory(
        n_res=n_res,
        t_type=t_conf["type"],
        box_size=t_conf["box"],
        device=config.DEVICE,
        target_name=target,
    )
    ff = ForceField(
        top=top,
        params=ff_params,
        neighbor_settings=neighbor_settings,
        force_backend=force_backend,
    ).to(config.DEVICE)
    return ff


def collect_feature_rows(args: argparse.Namespace) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    targets = _parse_targets(args.targets)
    export_internal_pdb = bool(getattr(args, "export_internal_pdb", False))
    internal_pdb_out_dir = str(getattr(args, "internal_pdb_out_dir", "")).strip() or "runs/internal_postprocessed_pdb"
    internal_pdb_max_per_target = max(0, int(getattr(args, "internal_pdb_max_per_target", 1)))
    if export_internal_pdb:
        os.makedirs(internal_pdb_out_dir, exist_ok=True)

    ff_params = {
        "d_e": 20.0,
        "eps_solv": 25.0,
        "sigma": 3.8,
        "r0": 4.2,
    }
    neighbor_settings = {
        "grid_spacing": float(args.cutoff),
        "cutoff": float(args.cutoff),
        "skin": float(args.skin),
        "max_neighbors": int(args.max_neighbors),
        "max_atoms_per_cell": int(args.max_atoms_per_cell),
        "rebuild_stride": int(args.rebuild_stride),
    }

    os.environ.setdefault("NBLIST_AUTOGROW", "1")
    os.environ.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")
    if args.force_rust:
        os.environ["FORCE_RUST_HIP"] = "1"
        os.environ.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")

    hydro_strength_base = float(HydrophobicLogic(config.DEVICE).hydrophobic_strength.item())
    control_prefix = str(getattr(args, "control_prefix", "control_")).strip() or "control_"
    observed_prefix = str(getattr(args, "observed_prefix", "observed_")).strip() or "observed_"
    perturb_enabled = bool(getattr(args, "enable_control_perturbation", False))
    perturb_seed = int(getattr(args, "control_perturbation_seed", 20260222))
    ionic_grid = _parse_float_grid(str(getattr(args, "perturb_ionic_strength_grid", "")), float(args.ionic_strength))
    ptm_grid = _parse_int_grid(str(getattr(args, "perturb_ptm_count_grid", "")), int(args.ptm_count_default))
    temp_end_grid = _parse_float_grid(str(getattr(args, "perturb_temperature_end_grid", "")), float(args.temperature_end))
    hydro_scale_grid = _parse_float_grid(str(getattr(args, "perturb_hydro_scale_grid", "")), 1.0)
    force_scale_mult_grid = _parse_float_grid(str(getattr(args, "perturb_force_scale_mult_grid", "")), 1.0)

    rows: List[Dict[str, Any]] = []
    summary_targets: List[Dict[str, Any]] = []
    total_frames = 0
    total_internal_pdb_written = 0

    for t_idx, target in enumerate(targets):
        t_conf = ResearchConstants.CHALLENGES[target]
        n_res = int(t_conf["n_res"])
        native = _load_native(target, n_res)
        native_theta0 = _bond_angles(native)
        native_phi0 = _dihedral_angles(native)
        ff = _make_forcefield(
            target=target,
            n_res=n_res,
            t_conf=t_conf,
            force_backend=args.force_backend,
            neighbor_settings=neighbor_settings,
            ff_params=ff_params,
        )
        box = torch.as_tensor(t_conf["box"], dtype=torch.float32, device=config.DEVICE).view(1, 1, 3)

        target_violations = 0
        target_rows_start = len(rows)
        target_saved_frames = 0
        target_internal_pdb_written = 0

        for sample_idx in range(int(args.samples)):
            generator = torch.Generator(device=config.DEVICE)
            seed_i = int(args.seed) + (t_idx * 1000) + sample_idx
            generator.manual_seed(seed_i)
            def _pick(values: Sequence[Any], tag: str) -> Any:
                if not values:
                    return None
                base = _stable_int_key(f"{target}|{seed_i}|{perturb_seed}|{tag}")
                idx = int((base + sample_idx) % len(values))
                return values[idx]
            if perturb_enabled:
                ionic_strength_i = float(_pick(ionic_grid, "ionic"))
                ptm_count_i = int(_pick(ptm_grid, "ptm"))
                temperature_end_i = float(_pick(temp_end_grid, "temp_end"))
                hydro_scale_i = float(_pick(hydro_scale_grid, "hydro_scale"))
                force_scale_mult_i = float(_pick(force_scale_mult_grid, "force_scale"))
            else:
                ionic_strength_i = float(args.ionic_strength)
                ptm_count_i = int(args.ptm_count_default)
                temperature_end_i = float(args.temperature_end)
                hydro_scale_i = 1.0
                force_scale_mult_i = 1.0
            cooling_rate_i = (float(temperature_end_i) - float(args.temperature_start)) / max(int(args.steps), 1)
            kbt_mean_i = 0.001987 * ((float(args.temperature_start) + float(temperature_end_i)) * 0.5)
            hydro_strength_i = float(hydro_strength_base * hydro_scale_i)
            c = native.unsqueeze(0) + torch.randn((1, n_res, 3), generator=generator, device=config.DEVICE) * float(
                args.noise
            )
            c = torch.remainder(c, box)

            prev_energy: Optional[float] = None
            frame_records: List[Dict[str, Any]] = []
            theta_series: List[np.ndarray] = []
            phi_series: List[np.ndarray] = []

            with torch.no_grad():
                for step in range(int(args.steps) + 1):
                    f_core, pe = ff.compute(c, None)
                    energy = float(pe.squeeze().item()) if pe.numel() > 0 else 0.0
                    force_scale = float(f_core.norm(dim=-1).mean().item())

                    py_sat_atoms = int(getattr(ff.sh, "_last_neighbor_saturated_atoms", 0))
                    rs_stats = getattr(ff.rust_backend, "last_neighbor_build_stats", {}) or {}
                    rs_cell_overflow = bool(rs_stats.get("cell_overflow", False))
                    rs_neighbor_saturated = bool(rs_stats.get("neighbor_saturated", False))
                    overflow_flag = bool(py_sat_atoms > 0 or rs_cell_overflow or rs_neighbor_saturated)

                    if prev_energy is None:
                        energy_drift_ratio = 0.0
                    else:
                        energy_drift_ratio = abs(energy - prev_energy) / (abs(prev_energy) + 1e-8)
                    violation = int(
                        overflow_flag or (energy_drift_ratio > float(args.energy_drift_threshold))
                    )
                    target_violations += violation

                    save_this = (step % int(args.save_stride) == 0) or (step == int(args.steps))
                    if save_this:
                        coords = c.squeeze(0).detach()
                        rg = calculate_rg(coords)
                        sasa = calculate_sasa_proxy(coords, cutoff=float(args.sasa_cutoff))
                        compactness, cluster_max = _compactness_and_cluster(
                            coords,
                            cutoff=float(args.contact_cutoff),
                            max_neighbors=int(args.contact_diagnostic_max_neighbors),
                        )
                        rmsd = _rmsd(coords, native)
                        is_llps = int(
                            (cluster_max / max(float(n_res), 1.0)) >= float(args.llps_cluster_fraction_threshold)
                            and compactness >= float(args.llps_compactness_threshold)
                        )
                        is_folded = int(rmsd <= float(args.folded_rmsd_threshold))
                        theta = _bond_angles(coords).detach().cpu().numpy().astype(np.float32)
                        phi = _dihedral_angles(coords).detach().cpu().numpy().astype(np.float32)
                        theta_series.append(theta)
                        phi_series.append(phi)
                        frame_records.append(
                            {
                                "target": target,
                                "sample_idx": int(sample_idx),
                                "seed": int(seed_i),
                                "step": int(step),
                                "energy": float(energy),
                                "Rg": float(rg),
                                "compactness": float(compactness),
                                "sasa": float(sasa),
                                "cluster_max": int(cluster_max),
                                "is_llps": int(is_llps),
                                "is_folded": int(is_folded),
                                "rmsd": float(rmsd),
                                "ionic_strength": float(ionic_strength_i),
                                "ptm_count": int(ptm_count_i),
                                "force_scale": float(force_scale),
                                "cooling_rate": float(cooling_rate_i),
                                "hydro_strength": float(hydro_strength_i),
                                "violations": int(violation),
                                "ai_correction_active": int(bool(args.ai_correction_active)),
                                "energy_drift_ratio": float(energy_drift_ratio),
                                "overflow_flag": int(overflow_flag),
                                "neighbor_saturated_atoms_py": int(py_sat_atoms),
                                "neighbor_saturated_rs": int(rs_neighbor_saturated),
                                "cell_overflow_rs": int(rs_cell_overflow),
                                "proxy_energy": float(calculate_proxy_energy(coords)),
                                f"{control_prefix}ionic_strength": float(ionic_strength_i),
                                f"{control_prefix}ptm_count": int(ptm_count_i),
                                f"{control_prefix}cooling_rate": float(cooling_rate_i),
                                f"{control_prefix}hydro_strength": float(hydro_strength_i),
                                f"{control_prefix}force_scale_mult": float(force_scale_mult_i),
                                f"{control_prefix}temperature_start": float(args.temperature_start),
                                f"{control_prefix}temperature_end": float(temperature_end_i),
                                f"{observed_prefix}is_llps": int(is_llps),
                                f"{observed_prefix}is_folded": int(is_folded),
                                f"{observed_prefix}rmsd": float(rmsd),
                                f"{observed_prefix}violations": int(violation),
                            }
                        )

                    if step < int(args.steps):
                        f_total = f_core - float(args.restraint_k) * (c - native.unsqueeze(0))
                        f_total = f_total * float(force_scale_mult_i)
                        if float(args.force_clip) > 0.0:
                            f_total = torch.clamp(
                                f_total,
                                min=-float(args.force_clip),
                                max=float(args.force_clip),
                            )
                        c = c + float(args.dt) * f_total
                        c = torch.remainder(c, box)
                    prev_energy = energy

            if len(frame_records) == 0:
                continue

            if export_internal_pdb and (target_internal_pdb_written < internal_pdb_max_per_target):
                final_coords_wrapped = c.squeeze(0).detach().cpu().numpy().astype(np.float32, copy=False)
                box_vec = box.squeeze(0).squeeze(0).detach().cpu().numpy().astype(np.float32, copy=False)
                final_coords = _unwrap_polymer_coords(final_coords_wrapped, box_vec)
                out_name = (
                    f"internal_post_{_slug(target)}_sample{int(sample_idx):03d}_"
                    f"step{int(args.steps):05d}.pdb"
                )
                out_path = os.path.join(internal_pdb_out_dir, out_name)
                _write_internal_postprocessed_pdb(
                    out_path=out_path,
                    coords=final_coords,
                    target=target,
                    sample_idx=int(sample_idx),
                    step=int(args.steps),
                )
                target_internal_pdb_written += 1
                total_internal_pdb_written += 1

            theta_mat = np.stack(theta_series, axis=0) if theta_series else np.zeros((0, n_res), dtype=np.float32)
            phi_mat = np.stack(phi_series, axis=0) if phi_series else np.zeros((0, n_res), dtype=np.float32)
            k_angle = _nanvar_k(theta_mat, kbt_mean_i)
            k_dihedral = _nanvar_k(phi_mat, kbt_mean_i)
            theta0_np = native_theta0.detach().cpu().numpy().astype(np.float32)
            phi0_np = native_phi0.detach().cpu().numpy().astype(np.float32)

            for f_idx, fr in enumerate(frame_records):
                theta_row = theta_mat[f_idx]
                phi_row = phi_mat[f_idx]
                for residue_idx in range(n_res):
                    row = {
                        **fr,
                        "residue_idx": int(residue_idx),
                        "k_angle": _float_or_none(k_angle[residue_idx]) if residue_idx < len(k_angle) else None,
                        "theta0": _float_or_none(theta0_np[residue_idx]) if residue_idx < len(theta0_np) else None,
                        "k_dihedral": _float_or_none(k_dihedral[residue_idx])
                        if residue_idx < len(k_dihedral)
                        else None,
                        "phi0_alpha": _float_or_none(phi0_np[residue_idx]) if residue_idx < len(phi0_np) else None,
                        # Raw instantaneous geometric observables are logged for later fitting.
                        "theta": _float_or_none(theta_row[residue_idx]),
                        "phi": _float_or_none(phi_row[residue_idx]),
                    }
                    rows.append(row)
                    target_saved_frames += 1
                    total_frames += 1

        target_row_count = len(rows) - target_rows_start
        summary_targets.append(
            {
                "target": target,
                "n_res": n_res,
                "rows": int(target_row_count),
                "samples": int(args.samples),
                "steps": int(args.steps),
                "save_stride": int(args.save_stride),
                "total_violations": int(target_violations),
                "saved_frame_residue_rows": int(target_saved_frames),
                "internal_pdb_written": int(target_internal_pdb_written),
            }
        )

    summary = {
        "targets": summary_targets,
        "total_targets": int(len(targets)),
        "total_rows": int(len(rows)),
        "total_saved_frame_residue_rows": int(total_frames),
        "params_covered": [
            "energy",
            "Rg",
            "compactness",
            "sasa",
            "cluster_max",
            "is_llps",
            "is_folded",
            "rmsd",
            "ionic_strength",
            "ptm_count",
            "force_scale",
            "cooling_rate",
            "hydro_strength",
            "k_angle",
            "theta0",
            "k_dihedral",
            "phi0_alpha",
            "violations",
            "ai_correction_active",
        ],
        "notes": [
            "k_angle and k_dihedral are variance-derived proxies from sampled trajectory frames",
            "theta0 and phi0_alpha are native-structure geometric references per residue",
            "ai_correction_active is run mode flag in this collector (default false)",
        ],
        "schema": {
            "control_prefix": str(control_prefix),
            "observed_prefix": str(observed_prefix),
            "control_columns": [
                f"{control_prefix}ionic_strength",
                f"{control_prefix}ptm_count",
                f"{control_prefix}cooling_rate",
                f"{control_prefix}hydro_strength",
                f"{control_prefix}force_scale_mult",
                f"{control_prefix}temperature_start",
                f"{control_prefix}temperature_end",
            ],
            "observed_columns": [
                f"{observed_prefix}is_llps",
                f"{observed_prefix}is_folded",
                f"{observed_prefix}rmsd",
                f"{observed_prefix}violations",
            ],
        },
        "control_perturbation": {
            "enabled": bool(perturb_enabled),
            "seed": int(perturb_seed),
            "ionic_strength_grid": [float(x) for x in ionic_grid],
            "ptm_count_grid": [int(x) for x in ptm_grid],
            "temperature_end_grid": [float(x) for x in temp_end_grid],
            "hydro_scale_grid": [float(x) for x in hydro_scale_grid],
            "force_scale_mult_grid": [float(x) for x in force_scale_mult_grid],
        },
        "internal_pdb_export": {
            "enabled": bool(export_internal_pdb),
            "out_dir": internal_pdb_out_dir if export_internal_pdb else "",
            "max_per_target": int(internal_pdb_max_per_target),
            "total_written": int(total_internal_pdb_written),
        },
    }
    return rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect per-target/per-step/per-residue feature matrix for 19 core parameters."
    )
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--save-stride", type=int, default=10)
    parser.add_argument("--noise", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--dt", type=float, default=1e-5)
    parser.add_argument("--restraint-k", type=float, default=3.0)
    parser.add_argument("--force-clip", type=float, default=200.0)
    parser.add_argument("--cutoff", type=float, default=12.0)
    parser.add_argument("--skin", type=float, default=2.0)
    parser.add_argument("--max-neighbors", type=int, default=100)
    parser.add_argument("--max-atoms-per-cell", type=int, default=64)
    parser.add_argument("--rebuild-stride", type=int, default=4)
    parser.add_argument("--contact-cutoff", type=float, default=8.0)
    parser.add_argument(
        "--contact-diagnostic-max-neighbors",
        type=int,
        default=DEFAULT_CONTACT_DIAGNOSTIC_MAX_NEIGHBORS,
    )
    parser.add_argument(
        "--max-dense-diagnostic-atoms",
        type=int,
        default=DEFAULT_CONTACT_DIAGNOSTIC_MAX_NEIGHBORS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--sasa-cutoff", type=float, default=8.0)
    parser.add_argument("--llps-cluster-fraction-threshold", type=float, default=0.75)
    parser.add_argument("--llps-compactness-threshold", type=float, default=0.15)
    parser.add_argument("--folded-rmsd-threshold", type=float, default=2.0)
    parser.add_argument("--energy-drift-threshold", type=float, default=0.30)
    parser.add_argument("--temperature-start", type=float, default=300.0)
    parser.add_argument("--temperature-end", type=float, default=300.0)
    parser.add_argument("--ionic-strength", type=float, default=0.15)
    parser.add_argument("--ptm-count-default", type=int, default=0)
    parser.add_argument("--enable-control-perturbation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--control-perturbation-seed", type=int, default=20260222)
    parser.add_argument("--perturb-ionic-strength-grid", type=str, default="0.05,0.15,0.30,0.50")
    parser.add_argument("--perturb-ptm-count-grid", type=str, default="0,1,2,3")
    parser.add_argument("--perturb-temperature-end-grid", type=str, default="300,350,400,500")
    parser.add_argument("--perturb-hydro-scale-grid", type=str, default="0.8,1.0,1.2")
    parser.add_argument("--perturb-force-scale-mult-grid", type=str, default="0.9,1.0,1.1")
    parser.add_argument("--control-prefix", type=str, default="control_")
    parser.add_argument("--observed-prefix", type=str, default="observed_")
    parser.add_argument("--ai-correction-active", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--force-rust", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-backend", type=str, default="auto", choices=["auto", "pytorch"])
    parser.add_argument(
        "--export-internal-pdb",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Export internal postprocessed structure snapshots as CA-projected PDB files.",
    )
    parser.add_argument(
        "--internal-pdb-out-dir",
        type=str,
        default="",
        help="Output directory for --export-internal-pdb.",
    )
    parser.add_argument(
        "--internal-pdb-max-per-target",
        type=int,
        default=1,
        help="Maximum internal postprocessed PDB files written per target.",
    )
    parser.add_argument("--out-csv", type=str, default="runs/feature_matrix_per_target.csv")
    parser.add_argument("--out-json", type=str, default="runs/feature_matrix_summary.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    rows, summary = collect_feature_rows(args)

    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(args.out_csv, index=False)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote CSV: {args.out_csv} rows={len(df)}")
    print(f"Wrote JSON: {args.out_json}")
    print(json.dumps({"total_targets": summary["total_targets"], "total_rows": summary["total_rows"]}, indent=2))


if __name__ == "__main__":
    main()
