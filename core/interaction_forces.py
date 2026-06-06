"""Minimal analytic interaction forces for O(N) neighbor-list physics."""

from __future__ import annotations

import torch


def _neighbor_displacement(c: torch.Tensor, nb_data: tuple[torch.Tensor, torch.Tensor, torch.Tensor]) -> torch.Tensor:
    nb_idx, _nb_dist, nb_mask = nb_data
    b, n, _ = c.shape
    k = int(nb_idx.shape[-1])
    batch_idx = torch.arange(b, device=c.device).view(b, 1, 1).expand(b, n, k)
    neighbor_pos = c[batch_idx, nb_idx]
    center = c.unsqueeze(2)
    dr = neighbor_pos - center
    return dr * nb_mask.unsqueeze(-1).to(dtype=dr.dtype)


def analytic_hbond_forces(
    c: torch.Tensor,
    nb_data: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    *,
    strength: float = -1.0,
    ideal_dist: float = 2.9,
    width: float = 0.45,
) -> torch.Tensor:
    """Distance-based H-bond attraction on neighbor pairs."""
    nb_idx, nb_dist, nb_mask = nb_data
    dr = _neighbor_displacement(c, nb_data)
    dist = nb_dist.clamp_min(1e-6)
    weight = torch.exp(-((dist - float(ideal_dist)) / float(width)) ** 2)
    weight = weight * nb_mask.to(dtype=weight.dtype)
    unit = dr / dist.unsqueeze(-1)
    pair_force = unit * (float(strength) * weight).unsqueeze(-1)
    denom = nb_mask.sum(dim=2, keepdim=True).clamp_min(1).to(dtype=pair_force.dtype)
    return pair_force.sum(dim=2) / denom


def analytic_hydrophobic_forces(
    c: torch.Tensor,
    nb_data: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    *,
    strength: float = 0.3,
    contact_dist: float = 4.5,
) -> torch.Tensor:
    """Soft attraction for hydrophobic contacts within cutoff."""
    nb_idx, nb_dist, nb_mask = nb_data
    dr = _neighbor_displacement(c, nb_data)
    dist = nb_dist.clamp_min(1e-6)
    gap = (float(contact_dist) - dist).clamp_min(0.0)
    weight = gap * nb_mask.to(dtype=gap.dtype)
    unit = dr / dist.unsqueeze(-1)
    pair_force = -unit * (float(strength) * weight).unsqueeze(-1)
    denom = nb_mask.sum(dim=2, keepdim=True).clamp_min(1).to(dtype=pair_force.dtype)
    return pair_force.sum(dim=2) / denom
