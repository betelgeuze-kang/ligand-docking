from __future__ import annotations

from dataclasses import dataclass

import torch

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import NeighborPairs, full_neighbor_pairs, neighbor_displacements, neighbor_upper_mask
from betelgeuze_engine.physics.term_claim_metadata import term_claim_metadata


@dataclass
class LegacyLJTerm:
    sigma: float = 3.8
    epsilon: float = 0.2
    cutoff: float | None = None
    name: str = "legacy_lj"

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        coords = state.coords.detach().clone().requires_grad_(True)
        pairs = pairs or full_neighbor_pairs(coords, cutoff=self.cutoff)
        delta = neighbor_displacements(coords, pairs)
        dist = delta.norm(dim=-1).clamp_min(1e-4)
        sigma = torch.tensor(float(self.sigma), dtype=coords.dtype, device=coords.device)
        epsilon = torch.tensor(float(self.epsilon), dtype=coords.dtype, device=coords.device)
        dist = torch.where(pairs.mask, dist, torch.ones_like(dist) * sigma)
        inv = sigma / dist
        pair_energy = 4.0 * epsilon * (inv.pow(12) - inv.pow(6))
        mask = neighbor_upper_mask(pairs).to(device=coords.device)
        energy = (pair_energy * mask.to(dtype=pair_energy.dtype)).sum(dim=(1, 2))
        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        return TermResult(
            energy=energy.detach(),
            forces=(-grad).detach(),
            diagnostics={
                "term": self.name,
                "status": "pass",
                "sigma": float(self.sigma),
                "epsilon": float(self.epsilon),
                "active_pair_count": int(mask.sum().item()),
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_sigma": float(self.sigma),
                    "force_term_epsilon": float(self.epsilon),
                    "force_term_active_pair_count": int(mask.sum().item()),
                },
            ),
        )
