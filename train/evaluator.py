# train/evaluator.py

import torch
import numpy as np
from contextlib import nullcontext
from betelgeuze_engine_v2.geometry import (
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from train.runtime_inputs import build_runtime_inputs, current_runtime_input_schema_metadata


def _unpack_batch(batch):
    if not isinstance(batch, (tuple, list)):
        raise TypeError(f"Unsupported batch type: {type(batch)}")
    if len(batch) == 3:
        coords_batch, target_forces_batch, residue_types_batch = batch
        return coords_batch, target_forces_batch, residue_types_batch, None, None
    if len(batch) == 4:
        coords_batch, target_forces_batch, residue_types_batch, quality_batch = batch
        return coords_batch, target_forces_batch, residue_types_batch, quality_batch, None
    if len(batch) == 5:
        coords_batch, target_forces_batch, residue_types_batch, quality_batch, sim_params_batch = batch
        return coords_batch, target_forces_batch, residue_types_batch, quality_batch, sim_params_batch
    raise ValueError(f"Unsupported batch size: {len(batch)}")


def _pairwise_lj_energy(
    coords: torch.Tensor,
    sigma: float = 3.8,
    eps: float = 25.0,
    cutoff: float = 12.0,
) -> torch.Tensor:
    """Reference local LJ metric evaluated on compact, unique sparse pairs."""

    bsz, n_atoms, _ = coords.shape
    if n_atoms <= 1:
        return torch.zeros((bsz,), device=coords.device, dtype=coords.dtype)
    finite_samples = torch.isfinite(coords).all(dim=-1).all(dim=-1)
    if not bool(finite_samples.all().item()):
        energy = torch.full((bsz,), float("inf"), device=coords.device, dtype=coords.dtype)
        if bool(finite_samples.any().item()):
            energy[finite_samples] = _pairwise_lj_energy(
                coords[finite_samples],
                sigma=sigma,
                eps=eps,
                cutoff=cutoff,
            )
        return energy
    try:
        neighbors = build_compact_radius_graph(
            coords,
            RadiusGraphConfig(
                cutoff_angstrom=float(cutoff),
                max_neighbors=128,
                max_atoms_per_cell=128,
            ),
        )
    except NeighborOverflowError:
        return torch.full((bsz,), float("inf"), device=coords.device, dtype=coords.dtype)
    upper_mask = neighbors.upper_mask()
    if not bool(upper_mask.any().item()):
        return torch.zeros((bsz,), device=coords.device, dtype=coords.dtype)
    batch_indices = torch.nonzero(upper_mask, as_tuple=True)[0]
    r = neighbors.distances[upper_mask].clamp_min(2.0)
    inv = float(sigma) / r
    inv6 = inv.pow(6)
    inv12 = inv6.pow(2)
    e_pair = 4.0 * float(eps) * (inv12 - inv6)
    energy = torch.zeros((bsz,), device=coords.device, dtype=coords.dtype)
    return energy.index_add(0, batch_indices, e_pair)


def _sparse_overlap_flags(
    coords: torch.Tensor,
    *,
    threshold: float = 1.2,
) -> torch.Tensor:
    """Return one fail-closed overlap flag per sample without N-by-N storage."""

    batch_size, atom_count, _ = coords.shape
    finite_samples = torch.isfinite(coords).all(dim=-1).all(dim=-1)
    flags = ~finite_samples
    if atom_count <= 1:
        return flags
    valid_indices = torch.nonzero(finite_samples, as_tuple=True)[0]
    if valid_indices.numel() == 0:
        return flags
    try:
        neighbors = build_compact_radius_graph(
            coords[valid_indices],
            RadiusGraphConfig(
                cutoff_angstrom=float(threshold),
                max_neighbors=64,
                max_atoms_per_cell=64,
            ),
        )
    except NeighborOverflowError:
        # An overcrowded short-range cell is itself an invalid geometry for
        # this metric, so capacity overflow cannot accidentally pass the gate.
        flags[valid_indices] = True
        return flags
    edge_batches = torch.nonzero(neighbors.upper_mask(), as_tuple=True)[0]
    if edge_batches.numel():
        flags[valid_indices[edge_batches.unique()]] = True
    return flags


def evaluate_model(model, test_loader, device, metrics=['rmse', 'mae']):
    """
    Evaluate the trained model on a test set.
    Args:
        model (nn.Module): Trained model
        test_loader (DataLoader): Test data loader
        device (torch.device): Device to run evaluation
        metrics (list): List of metrics to compute (e.g., 'rmse', 'mae', 'energy_drift')
    Returns:
        results (dict): Dictionary containing computed metrics
    """
    model.eval()
    all_predictions = []
    all_targets = []
    all_coords = []
    use_amp = bool(getattr(device, "type", "cpu") == "cuda")
    amp_dtype = torch.bfloat16
    runtime_schema = current_runtime_input_schema_metadata()

    with torch.inference_mode():
        for batch_idx, batch in enumerate(test_loader):
            (
                coords_batch,
                target_forces_batch,
                residue_types_batch,
                _quality_batch,
                sim_params_batch,
            ) = _unpack_batch(batch)
            coords_batch = coords_batch.to(device, non_blocking=True)
            target_forces_batch = target_forces_batch.to(device, non_blocking=True)

            top_dummy, nb_data_dummy, pe_batch_dummy, sim_params_batch_dummy = build_runtime_inputs(
                coords_batch=coords_batch,
                residue_types_batch=residue_types_batch,
                sim_params_batch=sim_params_batch,
                neighbor_k=int(runtime_schema["neighbor_k"]),
                neighbor_cutoff_angstrom=float(runtime_schema["cutoff_angstrom"]),
                max_neighbor_candidates=int(runtime_schema["max_neighbor_candidates"]),
                max_atoms_per_cell=int(runtime_schema["max_atoms_per_cell"]),
            )

            autocast_ctx = (
                torch.autocast(
                    device_type=device.type,
                    dtype=amp_dtype,
                    enabled=True,
                )
                if use_amp
                else nullcontext()
            )
            with autocast_ctx:
                # Forward pass (with ai_influence=1.0 for evaluation)
                f_pred, _aux_out = model(
                    coords_batch,
                    top_dummy,
                    nb_data_dummy,
                    pe_batch_dummy,
                    sim_params_batch_dummy,
                    ai_influence=1.0,
                )

            all_predictions.append(f_pred.detach().cpu().numpy())
            all_targets.append(target_forces_batch.detach().cpu().numpy())
            all_coords.append(coords_batch.detach().cpu().numpy())

    if len(all_predictions) == 0:
        return {m: float('nan') for m in metrics}

    # Concatenate all predictions and targets
    pred_array = np.concatenate(all_predictions, axis=0) # [Total_Samples, N, 3]
    target_array = np.concatenate(all_targets, axis=0) # [Total_Samples, N, 3]
    coords_array = np.concatenate(all_coords, axis=0) # [Total_Samples, N, 3]

    results = {}
    for metric in metrics:
        if metric == 'rmse':
            rmse = np.sqrt(np.mean((pred_array - target_array)**2))
            results['rmse'] = rmse
        elif metric == 'mae':
            mae = np.mean(np.abs(pred_array - target_array))
            results['mae'] = mae
        elif metric == 'energy_drift':
            coords_t = torch.from_numpy(np.asarray(coords_array, dtype=np.float32)).to(device)
            pred_t = torch.from_numpy(np.asarray(pred_array, dtype=np.float32)).to(device)
            target_t = torch.from_numpy(np.asarray(target_array, dtype=np.float32)).to(device)
            dt = 1e-3
            c_next_pred = coords_t + pred_t * dt
            c_next_target = coords_t + target_t * dt
            e_pred = _pairwise_lj_energy(c_next_pred)
            e_target = _pairwise_lj_energy(c_next_target)
            finite_energy = torch.isfinite(e_pred) & torch.isfinite(e_target)
            drift_ratio = torch.full_like(e_pred, float("inf"))
            drift_ratio[finite_energy] = (
                (e_pred[finite_energy] - e_target[finite_energy]).abs()
                / e_target[finite_energy].abs().clamp_min(1e-6)
            )
            results['energy_drift'] = float(drift_ratio.mean().item())
        elif metric == 'violation_rate':
            coords_t = torch.from_numpy(np.asarray(coords_array, dtype=np.float32)).to(device)
            pred_t = torch.from_numpy(np.asarray(pred_array, dtype=np.float32)).to(device)
            target_t = torch.from_numpy(np.asarray(target_array, dtype=np.float32)).to(device)
            dt = 1e-3
            c_next_pred = coords_t + pred_t * dt

            force_norm_pred = pred_t.norm(dim=-1).mean(dim=-1)
            force_norm_target = target_t.norm(dim=-1).mean(dim=-1)
            force_ratio = force_norm_pred / force_norm_target.clamp_min(1e-6)
            huge_force = force_ratio > 3.0

            overlap = _sparse_overlap_flags(c_next_pred, threshold=1.2)
            nonfinite = ~torch.isfinite(pred_t).all(dim=-1).all(dim=-1)
            violation = nonfinite | huge_force | overlap
            results['violation_rate'] = float(violation.float().mean().item())
        else:
            print(f"Warning: Metric {metric} not implemented.")
            results[metric] = float('nan')

    return results

# Usage example:
# model = StrategicOrchestrator(device).to(device)
# model.load_state_dict(torch.load('path/to/best/model.pth'))
# test_dataset = AIRouterHDF5Dataset('data/target_test_data.h5')
# test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
# results = evaluate_model(model, test_loader, device, metrics=['rmse', 'mae'])
# print(results)
