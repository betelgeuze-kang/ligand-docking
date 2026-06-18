from __future__ import annotations

import torch

from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.force_term import ForceTerm
from betelgeuze_engine.physics.neighbor import NeighborPairs, full_neighbor_pairs


def finite_difference_force_error(
    term: ForceTerm,
    state: EngineState,
    *,
    atom_index: int = 0,
    coord_index: int = 0,
    epsilon: float = 1e-4,
) -> float:
    observed = term.energy_forces(state).forces[:, atom_index, coord_index].mean()
    plus = state.coords.detach().clone()
    minus = state.coords.detach().clone()
    plus[:, atom_index, coord_index] += float(epsilon)
    minus[:, atom_index, coord_index] -= float(epsilon)
    plus_state = EngineState(
        coords=plus,
        atom_types=state.atom_types,
        residue_types=state.residue_types,
        box=state.box,
        metadata=dict(state.metadata),
    )
    minus_state = EngineState(
        coords=minus,
        atom_types=state.atom_types,
        residue_types=state.residue_types,
        box=state.box,
        metadata=dict(state.metadata),
    )
    e_plus = term.energy_forces(plus_state).energy.mean()
    e_minus = term.energy_forces(minus_state).energy.mean()
    fd_force = -((e_plus - e_minus) / (2.0 * float(epsilon)))
    return float((observed - fd_force).abs().item())


def translation_invariance_error(
    term: ForceTerm,
    state: EngineState,
    shift: torch.Tensor,
) -> float:
    baseline = term.energy_forces(state)
    shifted_state = EngineState(
        coords=state.coords + shift.to(dtype=state.coords.dtype, device=state.coords.device),
        atom_types=state.atom_types,
        residue_types=state.residue_types,
        box=state.box,
        metadata=dict(state.metadata),
    )
    shifted = term.energy_forces(shifted_state)
    energy_err = (baseline.energy - shifted.energy).abs().amax()
    force_err = (baseline.forces - shifted.forces).abs().amax()
    return float(torch.maximum(energy_err, force_err).item())


def rotation_equivariance_error(
    term: ForceTerm,
    state: EngineState,
    rotation: torch.Tensor,
) -> float:
    baseline = term.energy_forces(state)
    rot = rotation.to(dtype=state.coords.dtype, device=state.coords.device)
    rotated_state = EngineState(
        coords=torch.matmul(state.coords, rot.transpose(-1, -2)),
        atom_types=state.atom_types,
        residue_types=state.residue_types,
        box=state.box,
        metadata=dict(state.metadata),
    )
    rotated = term.energy_forces(rotated_state)
    expected_forces = torch.matmul(baseline.forces, rot.transpose(-1, -2))
    energy_err = (baseline.energy - rotated.energy).abs().amax()
    force_err = (expected_forces - rotated.forces).abs().amax()
    return float(torch.maximum(energy_err, force_err).item())


def neighbor_list_parity_error(
    coords: torch.Tensor,
    *,
    cutoff: float,
    candidate_pairs: NeighborPairs | None = None,
) -> float:
    reference = full_neighbor_pairs(coords, cutoff=float(cutoff))
    observed = candidate_pairs or full_neighbor_pairs(coords, cutoff=float(cutoff))
    if observed.mask.shape != reference.mask.shape:
        return 1.0
    mismatch = (observed.mask != reference.mask).to(dtype=torch.float32)
    denom = max(int(reference.mask.numel()), 1)
    return float(mismatch.sum().item() / denom)


def energy_drift_smoke_pct(
    term: ForceTerm,
    state: EngineState,
    *,
    step_size: float = 1e-3,
) -> float:
    baseline = term.energy_forces(state)
    trial_coords = state.coords + float(step_size) * baseline.forces
    trial_state = EngineState(
        coords=trial_coords,
        atom_types=state.atom_types,
        residue_types=state.residue_types,
        box=state.box,
        metadata=dict(state.metadata),
    )
    trial = term.energy_forces(trial_state)
    denom = baseline.energy.abs().clamp_min(1e-6)
    drift = 100.0 * (trial.energy - baseline.energy).abs() / denom
    return float(drift.mean().item())
