from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch


def _default_claim_metadata() -> dict[str, Any]:
    return {
        "topology_fidelity": "not_assessed",
        "ligand_topology_valid": False,
        "hbond_evidence_status": "not_assessed",
        "force_residual_applied": False,
        "claim_safe": False,
        "blocked_reason": "term_result_unscoped",
    }


@dataclass
class TermResult:
    """Energy, force, and metadata result returned by every product force term."""

    energy: torch.Tensor
    forces: torch.Tensor
    diagnostics: dict[str, Any] = field(default_factory=dict)
    claim_metadata: dict[str, Any] = field(default_factory=_default_claim_metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "energy": self.energy.detach().cpu().tolist(),
            "forces_shape": list(self.forces.shape),
            "diagnostics": dict(self.diagnostics),
            "claim_metadata": dict(self.claim_metadata),
        }


@dataclass
class EnergyForces:
    energy: torch.Tensor
    forces: torch.Tensor
    terms: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    claim_metadata: dict[str, Any] = field(default_factory=_default_claim_metadata)
