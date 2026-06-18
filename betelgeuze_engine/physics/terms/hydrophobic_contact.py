from __future__ import annotations

from dataclasses import dataclass

import torch

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import NeighborPairs, full_neighbor_pairs
from betelgeuze_engine.physics.term_claim_metadata import term_claim_metadata


@dataclass
class HydrophobicContactTerm:
    strength: float = 0.2
    contact_dist: float = 4.5
    name: str = "hydrophobic_contact"

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        coords = state.coords.detach().clone().requires_grad_(True)
        pairs = pairs or full_neighbor_pairs(coords)
        hydrophobic = state.metadata.get("hydrophobic_mask")
        if hydrophobic is None:
            zero = torch.zeros(coords.shape[0], dtype=coords.dtype, device=coords.device)
            return TermResult(
                zero,
                torch.zeros_like(coords),
                {"term": self.name, "status": "mask_missing", "active_pair_count": 0},
                claim_metadata=term_claim_metadata(
                    state=state,
                    term_name=self.name,
                    status="mask_missing",
                    blocked_reason="hydrophobic_mask_missing",
                    extras={"force_term_active_pair_count": 0},
                ),
            )
        hydro = torch.as_tensor(hydrophobic, dtype=torch.bool, device=coords.device).reshape(-1)
        if int(hydro.numel()) != int(coords.shape[1]):
            raise ValueError("hydrophobic_mask length must match coords N")
        pair_role = hydro.view(1, -1, 1) & hydro.view(1, 1, -1)
        upper = torch.triu(torch.ones_like(pairs.mask, dtype=torch.bool), diagonal=1)
        mask = pairs.mask & pair_role & upper
        dist = (coords.unsqueeze(2) - coords.unsqueeze(1)).norm(dim=-1).clamp_min(1e-4)
        contact = torch.tensor(float(self.contact_dist), dtype=coords.dtype, device=coords.device)
        gap = (contact - dist).clamp_min(0.0)
        energy = (-0.5 * float(self.strength) * gap.pow(2) * mask.to(dtype=coords.dtype)).sum(dim=(1, 2))
        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        active_pair_count = int(mask.sum().item())
        return TermResult(
            energy=energy.detach(),
            forces=(-grad).detach(),
            diagnostics={"term": self.name, "status": "pass", "active_pair_count": active_pair_count},
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_contact_dist": float(self.contact_dist),
                },
            ),
        )
