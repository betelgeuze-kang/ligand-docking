"""Top-K-only force residual refinement hook."""

from __future__ import annotations

from typing import Any

import torch

from core.interaction_forces import analytic_hbond_forces, analytic_hydrophobic_forces

DEFAULT_TOP_K_FRACTION = 0.05


def should_apply_force_residual(*, rank_index: int, total_count: int, top_k_fraction: float = DEFAULT_TOP_K_FRACTION) -> bool:
    if int(total_count) <= 0:
        return False
    cutoff = max(1, int(float(total_count) * float(top_k_fraction)))
    return int(rank_index) < int(cutoff)


def refine_forces_shortlist(
    c: torch.Tensor,
    nb_data: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    f_core: torch.Tensor,
    *,
    hbond_strength: float = -0.5,
    hydrophobic_strength: float = 0.2,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Apply analytic residual forces for shortlist pose refinement."""
    f_hb = analytic_hbond_forces(c, nb_data, strength=float(hbond_strength))
    f_hy = analytic_hydrophobic_forces(c, nb_data, strength=float(hydrophobic_strength))
    f_residual = f_hb + f_hy
    f_total = f_core + f_residual
    meta = {
        "force_residual_applied": True,
        "hbond_mean_force": float(f_hb.norm(dim=-1).mean().item()),
        "hydrophobic_mean_force": float(f_hy.norm(dim=-1).mean().item()),
    }
    return f_total, meta
