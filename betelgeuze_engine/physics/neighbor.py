from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class NeighborPairs:
    idx: torch.Tensor
    dist: torch.Tensor
    mask: torch.Tensor


def full_neighbor_pairs(coords: torch.Tensor, *, cutoff: float | None = None) -> NeighborPairs:
    if coords.ndim != 3 or coords.shape[-1] != 3:
        raise ValueError("coords must have shape [B, N, 3]")
    b, n, _ = coords.shape
    device = coords.device
    idx = torch.arange(n, device=device).view(1, 1, n).expand(b, n, n)
    diff = coords.unsqueeze(2) - coords.unsqueeze(1)
    dist = diff.norm(dim=-1)
    mask = ~torch.eye(n, dtype=torch.bool, device=device).view(1, n, n).expand(b, n, n)
    if cutoff is not None:
        mask = mask & (dist <= float(cutoff))
    return NeighborPairs(idx=idx, dist=dist, mask=mask)
