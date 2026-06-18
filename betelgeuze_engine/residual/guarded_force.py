from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

import torch

from betelgeuze_engine.contracts.claim import default_claim_metadata


@dataclass(frozen=True)
class ForceResidualPolicy:
    max_abs_delta_score: float = 2.0
    top_k_rank_pct: float = 0.05
    max_force_norm: float = 25.0
    max_displacement: float = 0.25
    max_energy_drift_pct: float = 5.0
    abstain_uncertainty: float = 0.75
    step_size: float = 0.01

    @property
    def abstain_threshold(self) -> float:
        """Product-facing alias for the uncertainty abstention threshold."""
        return float(self.abstain_uncertainty)

    @property
    def max_energy_drift(self) -> float:
        """Product-facing alias for the percent energy-drift cap."""
        return float(self.max_energy_drift_pct)


@dataclass(frozen=True)
class ForceResidualDecision:
    apply: bool
    reason: str
    rank_pct: float
    topology_valid: bool
    uncertainty: float
    delta_score: float = 0.0

    @property
    def confidence(self) -> float:
        return float(max(0.0, min(1.0, 1.0 - float(self.uncertainty))))


@dataclass(frozen=True)
class ForceResidualReport:
    applied: bool
    max_force_norm: float
    energy_drift_pct: float
    displacement_rmsd: float
    skipped_reason: str
    delta_score: float = 0.0
    uncertainty: float = 0.0
    rank_pct: float = 1.0
    top_k_eligible: bool = False
    abstention_reason: str = ""
    claim_safe: bool = False
    policy_caps: dict[str, float] = field(default_factory=dict)

    @property
    def confidence(self) -> float:
        return float(max(0.0, min(1.0, 1.0 - float(self.uncertainty))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": bool(self.applied),
            "max_force_norm": float(self.max_force_norm),
            "energy_drift_pct": float(self.energy_drift_pct),
            "displacement_rmsd": float(self.displacement_rmsd),
            "skipped_reason": str(self.skipped_reason),
            "delta_score": float(self.delta_score),
            "uncertainty": float(self.uncertainty),
            "confidence": float(self.confidence),
            "rank_pct": float(self.rank_pct),
            "top_k_eligible": bool(self.top_k_eligible),
            "abstention_reason": str(self.abstention_reason),
            "claim_safe": bool(self.claim_safe),
            "policy_caps": dict(self.policy_caps),
        }

    def to_claim_metadata(self, base_claim_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = default_claim_metadata(**dict(base_claim_metadata or {}))
        metadata.update(
            {
                "force_residual_applied": bool(self.applied),
                "force_residual_claim_safe": bool(self.claim_safe),
                "force_residual_delta_score": float(self.delta_score),
                "force_residual_uncertainty": float(self.uncertainty),
                "force_residual_confidence": float(self.confidence),
                "force_residual_rank_pct": float(self.rank_pct),
                "force_residual_top_k_rank_pct": float(self.policy_caps.get("top_k_rank_pct", 0.0)),
                "force_residual_top_k_eligible": bool(self.top_k_eligible),
                "force_residual_max_force_norm": float(self.max_force_norm),
                "force_residual_energy_drift_pct": float(self.energy_drift_pct),
                "force_residual_displacement_rmsd": float(self.displacement_rmsd),
                "force_residual_skipped_reason": str(self.skipped_reason),
                "force_residual_abstention_reason": str(self.abstention_reason),
                "force_residual_abstain_threshold": float(
                    self.policy_caps.get(
                        "abstain_threshold",
                        self.policy_caps.get("abstain_uncertainty", 0.0),
                    )
                ),
                "force_residual_policy_caps": dict(self.policy_caps),
                "force_residual_status": "applied" if self.applied else "abstained",
            }
        )
        if not self.applied:
            metadata["claim_safe"] = False
            metadata["blocked_reason"] = str(self.skipped_reason or metadata.get("blocked_reason") or "force_residual_abstained")
        return metadata


def _policy_caps(policy: ForceResidualPolicy) -> dict[str, float]:
    return {
        "max_abs_delta_score": float(policy.max_abs_delta_score),
        "max_force_norm": float(policy.max_force_norm),
        "max_displacement": float(policy.max_displacement),
        "max_energy_drift": float(policy.max_energy_drift),
        "max_energy_drift_pct": float(policy.max_energy_drift_pct),
        "abstain_uncertainty": float(policy.abstain_uncertainty),
        "abstain_threshold": float(policy.abstain_threshold),
        "top_k_rank_pct": float(policy.top_k_rank_pct),
    }


def _report(
    *,
    applied: bool,
    max_force_norm: float,
    energy_drift_pct: float,
    displacement_rmsd: float,
    skipped_reason: str,
    policy: ForceResidualPolicy,
    delta_score: float = 0.0,
    uncertainty: float = 0.0,
    rank_pct: float = 1.0,
) -> ForceResidualReport:
    rank = float(rank_pct)
    top_k_eligible = bool(math.isfinite(rank) and 0.0 <= rank <= float(policy.top_k_rank_pct))
    return ForceResidualReport(
        applied=applied,
        max_force_norm=max_force_norm,
        energy_drift_pct=energy_drift_pct,
        displacement_rmsd=displacement_rmsd,
        skipped_reason=skipped_reason,
        delta_score=float(delta_score),
        uncertainty=float(uncertainty),
        rank_pct=rank,
        top_k_eligible=top_k_eligible,
        abstention_reason="" if applied else skipped_reason,
        claim_safe=applied,
        policy_caps=_policy_caps(policy),
    )


def decide_force_residual(
    *,
    rank_pct: float,
    topology_valid: bool,
    uncertainty: float,
    delta_score: float = 0.0,
    policy: ForceResidualPolicy | None = None,
) -> ForceResidualDecision:
    policy = policy or ForceResidualPolicy()
    rank = float(rank_pct)
    unc = float(uncertainty)
    delta = float(delta_score)
    if not math.isfinite(rank):
        return ForceResidualDecision(False, "rank_pct_nonfinite", rank, bool(topology_valid), unc, delta)
    if rank < 0.0 or rank > 1.0:
        return ForceResidualDecision(False, "rank_pct_out_of_range", rank, bool(topology_valid), unc, delta)
    if not math.isfinite(delta):
        return ForceResidualDecision(False, "delta_score_nonfinite", rank, bool(topology_valid), unc, delta)
    if abs(delta) > float(policy.max_abs_delta_score):
        return ForceResidualDecision(False, "delta_score_cap_exceeded", rank, bool(topology_valid), unc, delta)
    if rank > float(policy.top_k_rank_pct):
        return ForceResidualDecision(False, "outside_top_k_policy", rank, bool(topology_valid), unc, delta)
    if not bool(topology_valid):
        return ForceResidualDecision(False, "topology_invalid", rank, False, unc, delta)
    if unc >= float(policy.abstain_uncertainty):
        return ForceResidualDecision(False, "uncertainty_abstained", rank, True, unc, delta)
    return ForceResidualDecision(True, "apply", rank, True, unc, delta)


def _energy_drift_pct(energy_before: float | None, energy_after: float | None) -> float:
    if energy_before is None or energy_after is None:
        return 0.0
    denom = max(abs(float(energy_before)), 1e-6)
    return float(100.0 * abs(float(energy_after) - float(energy_before)) / denom)


def apply_guarded_force_residual(
    coords: torch.Tensor,
    forces: torch.Tensor,
    *,
    decision: ForceResidualDecision,
    policy: ForceResidualPolicy | None = None,
    energy_before: float | None = None,
    energy_after: float | None = None,
) -> tuple[torch.Tensor, ForceResidualReport]:
    policy = policy or ForceResidualPolicy()
    if coords.shape != forces.shape:
        raise ValueError("coords and forces must have the same shape")
    max_force_norm = float(forces.norm(dim=-1).amax().item()) if forces.numel() else 0.0
    drift = _energy_drift_pct(energy_before, energy_after)
    if not decision.apply:
        return coords, _report(
            applied=False,
            max_force_norm=max_force_norm,
            energy_drift_pct=drift,
            displacement_rmsd=0.0,
            skipped_reason=decision.reason,
            policy=policy,
            delta_score=decision.delta_score,
            uncertainty=decision.uncertainty,
            rank_pct=decision.rank_pct,
        )
    if abs(float(decision.delta_score)) > float(policy.max_abs_delta_score):
        return coords, _report(
            applied=False,
            max_force_norm=max_force_norm,
            energy_drift_pct=drift,
            displacement_rmsd=0.0,
            skipped_reason="delta_score_cap_exceeded",
            policy=policy,
            delta_score=decision.delta_score,
            uncertainty=decision.uncertainty,
            rank_pct=decision.rank_pct,
        )
    if max_force_norm > float(policy.max_force_norm):
        return coords, _report(
            applied=False,
            max_force_norm=max_force_norm,
            energy_drift_pct=drift,
            displacement_rmsd=0.0,
            skipped_reason="max_force_norm_exceeded",
            policy=policy,
            delta_score=decision.delta_score,
            uncertainty=decision.uncertainty,
            rank_pct=decision.rank_pct,
        )
    if drift > float(policy.max_energy_drift_pct):
        return coords, _report(
            applied=False,
            max_force_norm=max_force_norm,
            energy_drift_pct=drift,
            displacement_rmsd=0.0,
            skipped_reason="energy_drift_exceeded",
            policy=policy,
            delta_score=decision.delta_score,
            uncertainty=decision.uncertainty,
            rank_pct=decision.rank_pct,
        )

    delta = float(policy.step_size) * forces
    norms = delta.norm(dim=-1, keepdim=True)
    cap = torch.tensor(float(policy.max_displacement), dtype=coords.dtype, device=coords.device)
    scale = torch.clamp(cap / norms.clamp_min(1e-12), max=1.0)
    bounded_delta = delta * scale
    updated = coords + bounded_delta
    displacement_rmsd = float(bounded_delta.pow(2).sum(dim=-1).mean().sqrt().item()) if bounded_delta.numel() else 0.0
    if not torch.isfinite(updated).all():
        return coords, _report(
            applied=False,
            max_force_norm=max_force_norm,
            energy_drift_pct=drift,
            displacement_rmsd=displacement_rmsd,
            skipped_reason="nonfinite_update",
            policy=policy,
            delta_score=decision.delta_score,
            uncertainty=decision.uncertainty,
            rank_pct=decision.rank_pct,
        )
    return updated, _report(
        applied=True,
        max_force_norm=max_force_norm,
        energy_drift_pct=drift,
        displacement_rmsd=displacement_rmsd,
        skipped_reason="",
        policy=policy,
        delta_score=decision.delta_score,
        uncertainty=decision.uncertainty,
        rank_pct=decision.rank_pct,
    )
