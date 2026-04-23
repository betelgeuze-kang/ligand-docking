# train/evaluator.py

import torch
import numpy as np
from contextlib import nullcontext
from torch.utils.data import DataLoader
from train.dataset import AIRouterHDF5Dataset
from train.runtime_inputs import build_runtime_inputs


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


def _pairwise_lj_energy(coords: torch.Tensor, sigma: float = 3.8, eps: float = 25.0, cutoff: float = 12.0) -> torch.Tensor:
    bsz, n_atoms, _ = coords.shape
    if n_atoms <= 1:
        return torch.zeros((bsz,), device=coords.device, dtype=coords.dtype)
    dmat = torch.cdist(coords, coords)
    eye = torch.eye(n_atoms, device=coords.device, dtype=torch.bool).unsqueeze(0)
    dmat = dmat.masked_fill(eye, float("inf"))
    mask = dmat < float(cutoff)
    r = dmat.clamp_min(2.0)
    inv = float(sigma) / r
    inv6 = inv.pow(6)
    inv12 = inv6.pow(2)
    e_pair = 4.0 * float(eps) * (inv12 - inv6)
    e_pair = torch.where(mask, e_pair, torch.zeros_like(e_pair))
    return 0.5 * e_pair.sum(dim=(-1, -2))


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
                neighbor_k=10,
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
            drift_ratio = (e_pred - e_target).abs() / e_target.abs().clamp_min(1e-6)
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

            n_atoms = c_next_pred.shape[1]
            if n_atoms > 1:
                dmat = torch.cdist(c_next_pred, c_next_pred)
                eye = torch.eye(n_atoms, device=device, dtype=torch.bool).unsqueeze(0)
                dmat = dmat.masked_fill(eye, float("inf"))
                min_dist = dmat.min(dim=-1).values.min(dim=-1).values
                overlap = min_dist < 1.2
            else:
                overlap = torch.zeros_like(huge_force, dtype=torch.bool)
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
