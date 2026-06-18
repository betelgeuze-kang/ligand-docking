from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClaimMetadata:
    topology_fidelity: str = "placeholder_alanine"
    ligand_topology_valid: bool = False
    hbond_evidence_status: str = "not_assessed"
    force_residual_applied: bool = False
    claim_safe: bool = False
    blocked_reason: str = "not_assessed"
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "topology_fidelity": self.topology_fidelity,
            "ligand_topology_valid": bool(self.ligand_topology_valid),
            "hbond_evidence_status": self.hbond_evidence_status,
            "force_residual_applied": bool(self.force_residual_applied),
            "claim_safe": bool(self.claim_safe),
            "blocked_reason": self.blocked_reason,
        }
        payload.update(dict(self.extras))
        return payload


def default_claim_metadata(**overrides: Any) -> dict[str, Any]:
    base = ClaimMetadata().to_dict()
    base.update({k: v for k, v in overrides.items() if v is not None})
    return base
