from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, Mapping, Optional, Sequence, Tuple

import torch
import torch.nn.functional as F

from core.definitions import Config
from core.sim_param_schema import (
    CORE_SIM_PARAM_DEFAULTS,
    DEFAULT_RUNTIME_CONDITIONING_KEYS,
    LEAKAGE_BLOCKED_SIM_KEYS,
    coerce_sim_param_float,
)


def filter_runtime_conditioning_params(
    sim_params_batch: Optional[Mapping[str, object]],
    *,
    allowed_keys: Sequence[str] = DEFAULT_RUNTIME_CONDITIONING_KEYS,
    blocked_keys: Sequence[str] = LEAKAGE_BLOCKED_SIM_KEYS,
) -> Dict[str, object]:
    if not isinstance(sim_params_batch, Mapping):
        return {}

    blocked = set(blocked_keys)
    out: Dict[str, object] = {}
    for key in allowed_keys:
        if key in blocked:
            continue
        if key in sim_params_batch:
            out[key] = sim_params_batch[key]
    return out


def resolve_sim_params(
    sim_params_batch: Optional[Mapping[str, object]],
) -> Dict[str, float]:
    filtered = filter_runtime_conditioning_params(sim_params_batch)
    out = dict(CORE_SIM_PARAM_DEFAULTS)
    for key in CORE_SIM_PARAM_DEFAULTS.keys():
        raw = filtered.get(key, out[key])
        if torch.is_tensor(raw):
            if raw.numel() == 0:
                out[key] = float(out[key])
            else:
                out[key] = float(raw.float().mean().item())
        else:
            out[key] = coerce_sim_param_float(raw, out[key])

    for key, raw in filtered.items():
        if key in out:
            continue
        if torch.is_tensor(raw):
            if raw.numel() == 0:
                continue
            out[key] = float(raw.float().mean().item())
        else:
            out[key] = coerce_sim_param_float(raw, 0.0)
    return out


def _build_residue_features(
    residue_types_batch: torch.Tensor,
    topo_feature_dim: int,
) -> torch.Tensor:
    if residue_types_batch.dim() == 1:
        residue_types_batch = residue_types_batch.unsqueeze(0)
    residue_mod = residue_types_batch.long().clamp(min=0).remainder(int(topo_feature_dim))
    return F.one_hot(residue_mod, num_classes=int(topo_feature_dim)).float()


def _build_knn_neighbor_data(
    coords_batch: torch.Tensor,
    neighbor_k: int,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    bsz, n_atoms, _ = coords_batch.shape
    k_req = max(int(neighbor_k), 1)

    if n_atoms <= 1:
        nb_idx = torch.full((bsz, n_atoms, k_req), -1, dtype=torch.long, device=coords_batch.device)
        nb_dist = torch.zeros((bsz, n_atoms, k_req), dtype=coords_batch.dtype, device=coords_batch.device)
        nb_mask = torch.zeros((bsz, n_atoms, k_req), dtype=coords_batch.dtype, device=coords_batch.device)
        return nb_idx, nb_dist, nb_mask

    dmat = torch.cdist(coords_batch, coords_batch)
    eye = torch.eye(n_atoms, dtype=torch.bool, device=coords_batch.device).unsqueeze(0)
    dmat = dmat.masked_fill(eye, float("inf"))

    k_eff = min(k_req, n_atoms - 1)
    nb_dist_eff, nb_idx_eff = torch.topk(dmat, k=k_eff, dim=-1, largest=False)
    nb_mask_eff = torch.ones_like(nb_dist_eff, dtype=coords_batch.dtype)

    if k_eff == k_req:
        return nb_idx_eff.long(), nb_dist_eff, nb_mask_eff

    pad = k_req - k_eff
    pad_idx = torch.full((bsz, n_atoms, pad), -1, dtype=torch.long, device=coords_batch.device)
    pad_dist = torch.zeros((bsz, n_atoms, pad), dtype=coords_batch.dtype, device=coords_batch.device)
    pad_mask = torch.zeros((bsz, n_atoms, pad), dtype=coords_batch.dtype, device=coords_batch.device)
    nb_idx = torch.cat([nb_idx_eff.long(), pad_idx], dim=-1)
    nb_dist = torch.cat([nb_dist_eff, pad_dist], dim=-1)
    nb_mask = torch.cat([nb_mask_eff, pad_mask], dim=-1)
    return nb_idx, nb_dist, nb_mask


def build_runtime_inputs(
    coords_batch: torch.Tensor,
    residue_types_batch: torch.Tensor,
    *,
    sim_params_batch: Optional[Mapping[str, object]] = None,
    neighbor_k: int = 10,
):
    topo_feature_dim = int(getattr(Config, "TOPO_FEATURE_DIM", 64))
    residue_features = _build_residue_features(
        residue_types_batch=residue_types_batch.to(coords_batch.device),
        topo_feature_dim=topo_feature_dim,
    ).to(device=coords_batch.device, dtype=coords_batch.dtype)
    top_dummy = SimpleNamespace(
        residue_types=residue_types_batch.to(coords_batch.device),
        residue_features=residue_features,
    )

    nb_data = _build_knn_neighbor_data(coords_batch, neighbor_k=max(int(neighbor_k), 1))
    # Lightweight potential proxy for modules that expect PE tensor shape [B, 1].
    nb_dist = nb_data[1]
    pe_proxy = (1.0 / nb_dist.clamp_min(2.0)).mean(dim=(-1, -2), keepdim=False).unsqueeze(-1)
    sim_params = resolve_sim_params(sim_params_batch)
    return top_dummy, nb_data, pe_proxy, sim_params
