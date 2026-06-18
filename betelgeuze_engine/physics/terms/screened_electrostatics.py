from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import NeighborPairs, full_neighbor_pairs
from betelgeuze_engine.physics.term_claim_metadata import term_claim_metadata


def _metadata_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


@dataclass
class ScreenedElectrostaticsTerm:
    """Guarded screened Coulomb proxy for opt-in product force-term experiments."""

    scale: float = 4.0
    debye_kappa: float = 0.2
    cutoff: float | None = None
    name: str = "screened_electrostatics"

    def _zero_result(
        self,
        state: EngineState,
        coords: torch.Tensor,
        *,
        status: str,
        blocked_reason: str,
        charge_source: str = "",
    ) -> TermResult:
        zero = torch.zeros(coords.shape[0], dtype=coords.dtype, device=coords.device)
        return TermResult(
            energy=zero,
            forces=torch.zeros_like(coords),
            diagnostics={
                "term": self.name,
                "status": status,
                "active_pair_count": 0,
                "charge_source": charge_source,
                "scale": float(self.scale),
                "debye_kappa": float(self.debye_kappa),
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status=status,
                blocked_reason=blocked_reason,
                extras={
                    "force_term_active_pair_count": 0,
                    "force_term_charge_source": charge_source,
                    "force_term_charge_model_valid": False,
                    "force_term_debye_kappa": float(self.debye_kappa),
                    "force_term_scale": float(self.scale),
                },
            ),
        )

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        coords = state.coords.detach().clone().requires_grad_(True)
        metadata = dict(state.metadata)
        charges_value = _metadata_value(metadata, "partial_charges", "charges", "formal_charges")
        charge_source = str(metadata.get("charge_source") or "")
        if charges_value is None:
            return self._zero_result(
                state,
                coords,
                status="charges_missing",
                blocked_reason="screened_electrostatics_charges_missing",
                charge_source=charge_source,
            )
        charge_model_valid = metadata.get("charge_model_valid") is True
        if not charge_model_valid:
            return self._zero_result(
                state,
                coords,
                status="charge_model_unvalidated",
                blocked_reason="screened_electrostatics_charge_model_unvalidated",
                charge_source=charge_source,
            )
        charges = torch.as_tensor(charges_value, dtype=coords.dtype, device=coords.device).reshape(-1)
        if int(charges.numel()) != int(coords.shape[1]):
            return self._zero_result(
                state,
                coords,
                status="charge_length_mismatch",
                blocked_reason="screened_electrostatics_charge_length_mismatch",
                charge_source=charge_source,
            )

        pairs = pairs or full_neighbor_pairs(coords, cutoff=self.cutoff)
        dist = (coords.unsqueeze(2) - coords.unsqueeze(1)).norm(dim=-1).clamp_min(1e-4)
        upper = torch.triu(torch.ones_like(pairs.mask, dtype=torch.bool), diagonal=1)
        mask = pairs.mask & upper
        q_pair = charges.view(1, -1, 1) * charges.view(1, 1, -1)
        kappa = torch.tensor(float(self.debye_kappa), dtype=coords.dtype, device=coords.device).clamp_min(0.0)
        scale = torch.tensor(float(self.scale), dtype=coords.dtype, device=coords.device)
        pair_energy = scale * q_pair * torch.exp(-kappa * dist) / dist
        energy = (pair_energy * mask.to(dtype=pair_energy.dtype)).sum(dim=(1, 2))
        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        active_pair_count = int(mask.sum().item())
        return TermResult(
            energy=energy.detach(),
            forces=(-grad).detach(),
            diagnostics={
                "term": self.name,
                "status": "pass",
                "active_pair_count": active_pair_count,
                "charge_source": charge_source,
                "charge_count": int(charges.numel()),
                "scale": float(self.scale),
                "debye_kappa": float(self.debye_kappa),
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_charge_source": charge_source,
                    "force_term_charge_model_valid": True,
                    "force_term_charge_count": int(charges.numel()),
                    "force_term_debye_kappa": float(self.debye_kappa),
                    "force_term_scale": float(self.scale),
                },
            ),
        )
