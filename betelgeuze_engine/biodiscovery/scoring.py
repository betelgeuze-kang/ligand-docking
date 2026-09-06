from __future__ import annotations

import math
import time
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

from betelgeuze_engine.biodiscovery.stability_observations import (
    _coords as _observation_coordinates,
    measure_pose_retention,
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
) -> tuple[float | None, dict[str, Any]]:
    """Observe the existing clamped, force-clipped dynamics proxy truthfully.

    This is not a validated thermostat/integrator or binding stability estimate.
    Endpoint geometry is observed, not predicted. No physical-time or affinity
    inference is made. Preserve the legacy update formula, but never repair NaNs.
    """
    if isinstance(steps, (bool, np.bool_)) or not isinstance(steps, (int, np.integer)) or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    if not math.isfinite(dt) or dt <= 0. or not math.isfinite(temp_k) or temp_k < 0.:
        raise ValueError("dt must be positive and temp_k nonnegative, both finite")
    steps = int(steps)
    diagnostic: dict[str, Any] = {
        "schema_version": "tier_beta_stability_observation_v2",
        "status": "not_run",
        "evidence_kind": "computed_proxy_dynamics",
        "stable": None,
        "drift_A": None,
        "steps_requested": steps,
        "steps_run": 0,
        "initial_energy": None,
        "final_energy": None,
        "energy_drift": None,
        "energy_trace_length": 0,
        "elapsed_seconds": None,
        "pose_observations": {},
        "scientific_claim_validated": False,
        "stability_criterion": "receptor_aligned_ligand_endpoint_rmsd_lt_5a_proxy",
        "stability_criterion_calibrated": False,
        "force_clipped_component_count": 0,
        "coordinate_clamped_component_count": 0,
        "constraints": {
            "coordinate_clamp_box_a": float(DEFAULT_BOX_SIZE),
            "protein_ligand_constraints": "none_restricted_smoke",
        },
        "pbc_enabled": False,
        "neighbor_box_a": float(DEFAULT_BOX_SIZE),
        "coordinate_boundary": "clamp_not_periodic_wrapping",
        "thermostat": {"type": "langevin_proxy", "temperature_k": float(temp_k), "gamma": 1.0},
        "time_step": float(dt),
        "time_unit": "unvalidated_proxy_units",
        "restart_reproducible": None,
        "seeded_execution": True,
        "restart_seed": int(seed),
    }
    if steps == 0:
        diagnostic["thermostat"]["type"] = "not_run"
        return None, diagnostic

    dev = torch.device(device)
    if dev.type == "cuda":
        torch.cuda.synchronize(dev)
    started = time.perf_counter()

    def finish(drift: float | None) -> tuple[float | None, dict[str, Any]]:
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        diagnostic["elapsed_seconds"] = float(time.perf_counter() - started)
        return drift, diagnostic

    try:
        protein = _observation_coordinates(protein_beads, "protein_beads")
        ligand = _observation_coordinates(ligand_coords, "ligand_coords")
        coords = np.concatenate([protein, ligand], axis=0)
        if (np.abs(coords) > DEFAULT_BOX_SIZE / 2.).any():
            raise ValueError("initial_coordinates_outside_proxy_clamp_box")
        coords_t = torch.tensor(coords, dtype=torch.float32, device=dev).unsqueeze(0)
        # The observation baseline is the actual precision used by the integrator.
        initial = coords_t[0].detach().cpu().numpy().copy()
        atom_types = build_atom_types(len(protein), len(ligand), device=dev)
        state = EngineState(coords=coords_t, atom_types=atom_types)
        field = ProductForceField.from_registry(guarded_force_term_registry())
        generator = torch.Generator(device=dev).manual_seed(int(seed))
        provider = CellListNeighborProvider(NeighborProviderConfig(cutoff=8.0, skin=2.0, max_neighbor_count=64))
        kbt = 0.0019872041 * float(temp_k) / 298.15
        noise_scale = math.sqrt(2.0 * kbt * float(dt))

        def evaluate() -> tuple[torch.Tensor, float]:
            state.coords = coords_t.requires_grad_(True)
            pairs = provider.build(coords_t, box=DEFAULT_BOX_SIZE)
            pair_diag = dict(getattr(pairs, "diagnostics", {}) or {})
            if pair_diag.get("overflow") is True:
                raise ValueError("neighbor_overflow")
            if pair_diag.get("nxn_allocation_observed") is True or getattr(pairs, "is_dense", False):
                raise ValueError("dense_or_reference_neighbor")
            ef = field.energy_forces(state, pairs, product_neighbor_required=True)
            if not torch.isfinite(ef.energy).all() or not torch.isfinite(ef.forces).all():
                raise ValueError("nonfinite_energy_or_forces")
            if ef.forces.shape != coords_t.shape:
                raise ValueError("force_coordinate_shape_mismatch")
            energy = float(ef.energy.sum().detach().cpu().item())
            if not math.isfinite(energy):
                raise ValueError("nonfinite_total_energy")
            return ef.forces.detach(), energy

        for step_idx in range(steps):
            forces, energy = evaluate()
            if step_idx == 0:
                diagnostic["initial_energy"] = energy
            diagnostic["energy_trace_length"] += 1
            diagnostic["force_clipped_component_count"] += int((forces.abs() > 1.).sum().item())
            forces = forces.clamp(-1., 1.)
            noise = torch.randn(coords_t.shape, dtype=coords_t.dtype, device=dev, generator=generator) * noise_scale
            with torch.no_grad():
                updated = coords_t.detach() + forces * float(dt) + noise
                if not torch.isfinite(updated).all():
                    raise ValueError("nonfinite_updated_coordinates")
                diagnostic["coordinate_clamped_component_count"] += int((updated.abs() > DEFAULT_BOX_SIZE / 2.).sum().item())
                coords_t = updated.clamp(-DEFAULT_BOX_SIZE / 2., DEFAULT_BOX_SIZE / 2.)
            diagnostic["steps_run"] += 1

        # Evaluate the terminal coordinates, not the preceding step's energy.
        _, final_energy = evaluate()
        diagnostic["final_energy"] = final_energy
        diagnostic["energy_drift"] = final_energy - diagnostic["initial_energy"]
        final = coords_t[0].detach().cpu().numpy()
        observations = measure_pose_retention(initial[:len(protein)], initial[len(protein):],
                                              final[:len(protein)], final[len(protein):])
        drift = observations["ligand_rmsd_receptor_frame_a"]
        diagnostic.update(status="observed", pose_observations=observations, drift_A=drift,
                          stable=(drift < 5.0) if drift is not None else None)
        return finish(drift)
    except Exception as exc:
        diagnostic.update(status="failed", stable=False, error=str(exc),
                          error_step=diagnostic["steps_run"])
        return finish(None)
