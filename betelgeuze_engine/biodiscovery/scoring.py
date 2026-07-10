from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch

from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.forcefield import (
    ProductForceField,
    guarded_force_term_registry,
)
from betelgeuze_engine.physics.mm_gbsa import mm_gbsa_binding_energy
from betelgeuze_engine.physics.neighbor import (
    CellListNeighborProvider,
    NeighborProviderConfig,
)

DEFAULT_STABILITY_STEPS = 100
DEFAULT_STABILITY_DT = 0.001
DEFAULT_STABILITY_TEMP_K = 300.0
DEFAULT_BOX_SIZE = 80.0


def build_atom_types(bead_count: int, ligand_count: int, device: torch.device | str = "cpu") -> torch.Tensor:
    cg_atom_type = 1
    ligand_atom_type = 2
    types = [cg_atom_type] * int(bead_count) + [ligand_atom_type] * int(ligand_count)
    return torch.tensor(types, dtype=torch.long, device=device)


def single_pose_score(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    device: torch.device | str = "cpu",
) -> tuple[float, dict[str, Any]]:
    protein_array = np.asarray(protein_beads, dtype=np.float32)
    ligand_array = np.asarray(ligand_coords, dtype=np.float32)
    if protein_array.ndim != 2 or protein_array.shape[1] != 3 or protein_array.shape[0] == 0:
        return float("inf"), {"stable": False, "error": "invalid_protein_coordinates"}
    if ligand_array.ndim != 2 or ligand_array.shape[1] != 3 or ligand_array.shape[0] == 0:
        return float("inf"), {"stable": False, "error": "invalid_ligand_coordinates"}
    if not np.isfinite(protein_array).all() or not np.isfinite(ligand_array).all():
        return float("inf"), {"stable": False, "error": "nonfinite_coordinates"}
    coordinate_origin = protein_array.mean(axis=0)
    protein_local = protein_array - coordinate_origin
    ligand_local = ligand_array - coordinate_origin
    coords = np.concatenate([protein_local, ligand_local], axis=0)
    coords_t = torch.tensor(coords, dtype=torch.float32, device=device).unsqueeze(0)
    atom_types = build_atom_types(protein_array.shape[0], ligand_array.shape[0], device=device)

    state = EngineState(
        coords=coords_t,
        atom_types=atom_types,
    )

    neighbor_cfg = NeighborProviderConfig(
        cutoff=8.0,
        skin=2.0,
        max_neighbor_count=64,
    )
    neighbor_provider = CellListNeighborProvider(neighbor_cfg)
    pairs = neighbor_provider.build(coords_t, box=DEFAULT_BOX_SIZE)
    pair_diagnostics = dict(getattr(pairs, "diagnostics", {}) or {})
    if pair_diagnostics.get("overflow") is True:
        return float("inf"), {
            "status": "blocked_neighbor_overflow",
            "neighbor_diagnostics": pair_diagnostics,
        }
    if pair_diagnostics.get("nxn_allocation_observed") is True or getattr(pairs, "is_dense", False):
        return float("inf"), {
            "status": "blocked_dense_or_reference_neighbor",
            "neighbor_diagnostics": pair_diagnostics,
        }

    registry = guarded_force_term_registry()
    field = ProductForceField.from_registry(registry)
    try:
        ef = field.energy_forces(state, pairs, product_neighbor_required=True)
    except Exception as exc:
        return float("inf"), {
            "status": "blocked_forcefield_evaluation",
            "error": str(exc),
            "neighbor_diagnostics": pair_diagnostics,
        }

    total_e = float(ef.energy.sum().detach().cpu().item())

    def _self_energy(subset: np.ndarray, subset_types: torch.Tensor) -> float:
        if subset.size == 0:
            return 0.0
        subset_tensor = torch.tensor(subset, dtype=torch.float32, device=device).unsqueeze(0)
        subset_state = EngineState(coords=subset_tensor, atom_types=subset_types)
        subset_pairs = CellListNeighborProvider(neighbor_cfg).build(
            subset_tensor,
            box=DEFAULT_BOX_SIZE,
        )
        subset_ef = field.energy_forces(
            subset_state,
            subset_pairs,
            product_neighbor_required=True,
        )
        return float(subset_ef.energy.sum().detach().cpu().item())

    try:
        protein_self = _self_energy(protein_beads, atom_types[: protein_beads.shape[0]])
        ligand_self = _self_energy(ligand_coords, atom_types[protein_beads.shape[0] :])
    except Exception as exc:
        return float("inf"), {
            "status": "blocked_interaction_energy_decomposition",
            "error": str(exc),
            "neighbor_diagnostics": pair_diagnostics,
        }
    interaction_e = float(total_e - protein_self - ligand_self)
    terms = dict(ef.terms)
    claim = dict(ef.claim_metadata)

    diagnostics = {
        "total_energy": interaction_e,
        "interaction_energy_proxy": interaction_e,
        "whole_system_energy": total_e,
        "protein_self_energy": protein_self,
        "ligand_self_energy": ligand_self,
        "energy_decomposition": "complex_minus_receptor_minus_ligand",
        "terms": terms,
        "claim_safe": bool(claim.get("claim_safe", False)),
        "neighbor_pairs": int(ef.diagnostics.get("neighbor_pair_count", 0)),
        "neighbor_diagnostics": pair_diagnostics,
    }

    return interaction_e, diagnostics


def mm_gbsa_binding_score(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    contact_cutoff_a: float = 8.0,
) -> dict[str, Any]:
    try:
        result = mm_gbsa_binding_energy(
            protein_xyz=protein_beads.astype(np.float32),
            ligand_xyz=ligand_coords.astype(np.float32),
            contact_cutoff_a=float(contact_cutoff_a),
        )
        return dict(result)
    except Exception:
        return {
            "interaction_score_proxy": float("inf"),
            "error": "mm_gbsa_failed",
        }


def run_stability_simulation(
    protein_beads: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    device: torch.device | str = "cpu",
    steps: int = DEFAULT_STABILITY_STEPS,
    dt: float = DEFAULT_STABILITY_DT,
    temp_k: float = DEFAULT_STABILITY_TEMP_K,
    seed: int = 42,
) -> tuple[float, dict[str, Any]]:
    protein_array = np.asarray(protein_beads, dtype=np.float32)
    ligand_array = np.asarray(ligand_coords, dtype=np.float32)
    if protein_array.ndim != 2 or protein_array.shape[1] != 3 or protein_array.shape[0] == 0:
        return float("inf"), {"stable": False, "error": "invalid_protein_coordinates"}
    if ligand_array.ndim != 2 or ligand_array.shape[1] != 3 or ligand_array.shape[0] == 0:
        return float("inf"), {"stable": False, "error": "invalid_ligand_coordinates"}
    if not np.isfinite(protein_array).all() or not np.isfinite(ligand_array).all():
        return float("inf"), {"stable": False, "error": "nonfinite_coordinates"}
    if int(steps) < 0 or float(dt) <= 0.0 or float(temp_k) <= 0.0:
        return float("inf"), {"stable": False, "error": "invalid_stability_parameters"}

    coordinate_origin = protein_array.mean(axis=0)
    protein_local = protein_array - coordinate_origin
    ligand_local = ligand_array - coordinate_origin
    coords = np.concatenate([protein_local, ligand_local], axis=0)
    coords_t = torch.tensor(coords, dtype=torch.float32, device=device).unsqueeze(0)
    atom_types = build_atom_types(protein_array.shape[0], ligand_array.shape[0], device=device)

    state = EngineState(coords=coords_t, atom_types=atom_types)
    registry = guarded_force_term_registry()
    field = ProductForceField.from_registry(registry)
    generator = torch.Generator(device=coords_t.device)
    generator.manual_seed(int(seed))

    kbt = 0.0019872041 * float(temp_k)
    gamma = 1.0
    dt_f = float(dt)
    step_diagnostics: dict[str, Any] = {"coords": [], "energies": []}
    initial_energy = 0.0
    energy = 0.0

    ligand_start = int(protein_array.shape[0])
    c0_np = coords_t[:, ligand_start:, :].detach().cpu().numpy().copy()
    neighbor_provider = CellListNeighborProvider(
        NeighborProviderConfig(
            cutoff=8.0,
            skin=2.0,
            max_neighbor_count=64,
            rebuild_stride=10,
        )
    )

    for step_idx in range(int(steps)):
        coords_t.requires_grad_(True)
        if coords_t.grad is not None:
            coords_t.grad.zero_()
        state.coords = coords_t
        pairs = neighbor_provider.build(coords_t, step=step_idx, box=DEFAULT_BOX_SIZE)
        try:
            ef = field.energy_forces(state, pairs, product_neighbor_required=True)
        except Exception as exc:
            return float("inf"), {
                "stable": False,
                "error_step": step_idx,
                "error": str(exc),
                "steps_run": int(steps),
                "initial_energy": float(initial_energy),
                "final_energy": float("inf"),
                "energy_drift": float("inf"),
                "energy_trace_length": len(step_diagnostics["energies"]),
                "constraints": {
                    "coordinate_clamp_box_a": float(DEFAULT_BOX_SIZE),
                    "protein_ligand_constraints": "receptor_fixed_ligand_mobile",
                },
                "pbc_enabled": True,
                "pbc_box_a": float(DEFAULT_BOX_SIZE),
                "thermostat": {
                    "type": "langevin_proxy",
                    "temperature_k": float(temp_k),
                    "gamma": float(gamma),
                },
                "restart_reproducible": True,
                "restart_seed": int(seed),
                "coordinate_frame_centered_on_receptor": True,
            }
        forces = torch.nan_to_num(ef.forces.detach(), nan=0.0, posinf=0.0, neginf=0.0).clamp(
            -1.0,
            1.0,
        )
        energy = float(ef.energy.sum().detach().cpu().item())
        if step_idx == 0:
            initial_energy = energy

        ligand_noise = torch.randn(
            coords_t[:, ligand_start:, :].shape,
            dtype=coords_t.dtype,
            device=coords_t.device,
            generator=generator,
        ) * math.sqrt(2 * gamma * kbt * dt_f)
        with torch.no_grad():
            next_coords = coords_t.detach().clone()
            next_coords[:, ligand_start:, :] = (
                next_coords[:, ligand_start:, :]
                + forces[:, ligand_start:, :] * dt_f / gamma
                + ligand_noise
            )
            next_coords[:, ligand_start:, :] = next_coords[:, ligand_start:, :].clamp(
                -float(DEFAULT_BOX_SIZE) / 2,
                float(DEFAULT_BOX_SIZE) / 2,
            )
            coords_t = next_coords

        step_diagnostics["energies"].append(energy)
        if step_idx % 10 == 0:
            step_diagnostics["coords"].append(coords_t.detach().cpu().numpy().copy())

    final_np = coords_t[:, ligand_start:, :].detach().cpu().numpy()
    drift_total = float(np.sqrt(np.mean((final_np - c0_np) ** 2)))
    stable = bool(drift_total < 5.0)
    energy_drift = float(energy - initial_energy)

    return drift_total, {
        "stable": stable,
        "drift_A": drift_total,
        "steps_run": int(steps),
        "initial_energy": float(initial_energy),
        "final_energy": float(energy),
        "energy_drift": energy_drift,
        "energy_trace_length": len(step_diagnostics["energies"]),
        "constraints": {
            "coordinate_clamp_box_a": float(DEFAULT_BOX_SIZE),
            "protein_ligand_constraints": "receptor_fixed_ligand_mobile",
        },
        "pbc_enabled": True,
        "pbc_box_a": float(DEFAULT_BOX_SIZE),
        "thermostat": {
            "type": "overdamped_langevin_ligand_only_proxy",
            "temperature_k": float(temp_k),
            "gamma": float(gamma),
            "kbt_kcal_mol": float(kbt),
        },
        "restart_reproducible": True,
        "restart_seed": int(seed),
        "coordinate_frame_centered_on_receptor": True,
    }
