from __future__ import annotations

from dataclasses import dataclass

import torch

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import NeighborPairs, full_neighbor_pairs
from betelgeuze_engine.physics.term_claim_metadata import term_claim_metadata


@dataclass
class DirectionalHBondTerm:
    strength: float = 1.0
    ideal_dist: float = 2.9
    width: float = 0.45
    name: str = "directional_hbond"

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        coords = state.coords.detach().clone().requires_grad_(True)
        pairs = pairs or full_neighbor_pairs(coords)
        roles = list(state.metadata.get("hbond_roles", []))
        if len(roles) != int(coords.shape[1]):
            zero = torch.zeros(coords.shape[0], dtype=coords.dtype, device=coords.device)
            return TermResult(
                zero,
                torch.zeros_like(coords),
                {"term": self.name, "status": "roles_missing", "active_pair_count": 0},
                claim_metadata=term_claim_metadata(
                    state=state,
                    term_name=self.name,
                    status="roles_missing",
                    blocked_reason="hbond_roles_missing",
                    hbond_evidence_status="roles_missing",
                    extras={"force_term_active_pair_count": 0},
                ),
            )
        donor = torch.tensor([r in {"donor", "both"} for r in roles], dtype=torch.bool, device=coords.device)
        acceptor = torch.tensor([r in {"acceptor", "both"} for r in roles], dtype=torch.bool, device=coords.device)
        pair_role = (donor.view(1, -1, 1) & acceptor.view(1, 1, -1)) | (
            acceptor.view(1, -1, 1) & donor.view(1, 1, -1)
        )
        upper = torch.triu(torch.ones_like(pairs.mask, dtype=torch.bool), diagonal=1)
        mask = pairs.mask & pair_role & upper
        dist = (coords.unsqueeze(2) - coords.unsqueeze(1)).norm(dim=-1).clamp_min(1e-4)
        width = torch.tensor(float(self.width), dtype=coords.dtype, device=coords.device).clamp_min(1e-4)
        ideal = torch.tensor(float(self.ideal_dist), dtype=coords.dtype, device=coords.device)
        weight = torch.exp(-((dist - ideal) / width).pow(2))
        energy = (-float(self.strength) * weight * mask.to(dtype=coords.dtype)).sum(dim=(1, 2))
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
                hbond_evidence_status="pass" if active_pair_count > 0 else None,
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_ideal_dist": float(self.ideal_dist),
                    "force_term_width": float(self.width),
                },
            ),
        )
