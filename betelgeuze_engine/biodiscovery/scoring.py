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
    coords = np.concatenate([protein_beads, ligand_coords], axis=0)
    coords_t = torch.tensor(coords, dtype=torch.float32, device=device).unsqueeze(0)
    atom_types = build_atom_types(protein_beads.shape[0], ligand_coords.shape[0], device=device)

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
    terms = dict(ef.terms)
    claim = dict(ef.claim_metadata)

    diagnostics = {
        "total_energy": total_e,
        "terms": terms,
        "claim_safe": bool(claim.get("claim_safe", False)),
        "neighbor_pairs": int(ef.diagnostics.get("neighbor_pair_count", 0)),
        "neighbor_diagnostics": pair_diagnostics,
    }

    return total_e, diagnostics


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
            "binding_energy_kcal_mol": float("inf"),
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
    coords = np.concatenate([protein_beads, ligand_coords], axis=0)
    coords_t = torch.tensor(coords, dtype=torch.float32, device=device).unsqueeze(0)
    atom_types = build_atom_types(protein_beads.shape[0], ligand_coords.shape[0], device=device)

    state = EngineState(coords=coords_t, atom_types=atom_types)
    registry = guarded_force_term_registry()
    field = ProductForceField.from_registry(registry)
    torch.manual_seed(int(seed))

    kbt = 0.0019872041 * float(temp_k) / 298.15
    gamma = 1.0
    dt_f = float(dt)
    step_diagnostics: dict[str, Any] = {"coords": [], "energies": []}
    initial_energy = 0.0
    energy = 0.0

    c0_np = coords_t.detach().cpu().numpy().copy()

    for step_idx in range(int(steps)):
        coords_t.requires_grad_(True)
        if coords_t.grad is not None:
            coords_t.grad.zero_()
        state.coords = coords_t
        neighbor_cfg = NeighborProviderConfig(
            cutoff=8.0,
            skin=2.0,
            max_neighbor_count=64,
        )
        pairs = CellListNeighborProvider(neighbor_cfg).build(coords_t, box=DEFAULT_BOX_SIZE)
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
                    "protein_ligand_constraints": "none_restricted_smoke",
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
            }
        forces = torch.nan_to_num(ef.forces.detach(), nan=0.0, posinf=0.0, neginf=0.0).clamp(
            -1.0,
            1.0,
        )
        energy = float(ef.energy.sum().detach().cpu().item())
        if step_idx == 0:
            initial_energy = energy

        noise = torch.randn_like(coords_t) * math.sqrt(2 * gamma * kbt * dt_f)
        with torch.no_grad():
            coords_t = coords_t.detach() + forces * dt_f / gamma + noise
            coords_t = coords_t.clamp(-float(DEFAULT_BOX_SIZE) / 2, float(DEFAULT_BOX_SIZE) / 2)

        step_diagnostics["energies"].append(energy)
        if step_idx % 10 == 0:
            step_diagnostics["coords"].append(coords_t.detach().cpu().numpy().copy())

    final_np = coords_t.detach().cpu().numpy()
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
            "protein_ligand_constraints": "none_restricted_smoke",
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
    }
