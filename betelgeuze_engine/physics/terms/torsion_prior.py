from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import torch

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import NeighborPairs
from betelgeuze_engine.physics.term_claim_metadata import term_claim_metadata


def _metadata_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _quartet_tensor(value: Any, *, size: int, device: torch.device) -> torch.Tensor | None:
    if value is None:
        return None
    try:
        quartets = torch.as_tensor(value, dtype=torch.long, device=device).reshape(-1, 4)
    except (TypeError, ValueError, RuntimeError):
        return None
    if int(quartets.numel()) == 0:
        return None
    if bool(((quartets < 0) | (quartets >= int(size))).any().item()):
        return None
    sorted_quartets = torch.sort(quartets, dim=1).values
    if bool((sorted_quartets[:, 1:] == sorted_quartets[:, :-1]).any().item()):
        return None
    return quartets


def _target_tensor(value: Any, *, count: int, dtype: torch.dtype, device: torch.device) -> torch.Tensor | None:
    if value is None:
        return torch.zeros(count, dtype=dtype, device=device)
    try:
        targets = torch.as_tensor(value, dtype=dtype, device=device).reshape(-1)
    except (TypeError, ValueError, RuntimeError):
        return None
    if int(targets.numel()) == 1:
        targets = targets.expand(count)
    if int(targets.numel()) != int(count) or not bool(torch.isfinite(targets).all().item()):
        return None
    return targets


def _dihedral_angles(coords: torch.Tensor, quartets: torch.Tensor) -> torch.Tensor:
    p0 = coords[:, quartets[:, 0], :]
    p1 = coords[:, quartets[:, 1], :]
    p2 = coords[:, quartets[:, 2], :]
    p3 = coords[:, quartets[:, 3], :]

    b0 = p0 - p1
    b1 = p2 - p1
    b2 = p3 - p2
    b1_unit = b1 / b1.norm(dim=-1, keepdim=True).clamp_min(1e-9)
    v = b0 - (b0 * b1_unit).sum(dim=-1, keepdim=True) * b1_unit
    w = b2 - (b2 * b1_unit).sum(dim=-1, keepdim=True) * b1_unit
    x = (v * w).sum(dim=-1)
    y = (torch.cross(b1_unit, v, dim=-1) * w).sum(dim=-1)
    return torch.atan2(y, x)


@dataclass
class TorsionPriorTerm:
    """Guarded periodic torsion prior for validated ligand/topology quartets."""

    k_torsion: float = 0.15
    max_abs_energy: float = 50.0
    max_force_norm: float = 25.0
    max_active_pair_count: int = 4096
    name: str = "torsion_prior"

    def _policy_caps(self) -> dict[str, float]:
        return {
            "max_abs_energy": float(self.max_abs_energy),
            "max_force_norm": float(self.max_force_norm),
            "max_active_pair_count": float(self.max_active_pair_count),
        }

    def _policy_caps_ready(self) -> bool:
        return bool(
            math.isfinite(float(self.k_torsion))
            and float(self.k_torsion) >= 0.0
            and math.isfinite(float(self.max_abs_energy))
            and float(self.max_abs_energy) >= 0.0
            and math.isfinite(float(self.max_force_norm))
            and float(self.max_force_norm) > 0.0
            and int(self.max_active_pair_count) >= 0
        )

    def _cap_metadata(self, *, abs_energy: float, force_norm: float, active_pair_count: int) -> dict[str, Any]:
        energy_within_cap = bool(abs_energy <= float(self.max_abs_energy) + 1e-7)
        force_within_cap = bool(force_norm <= float(self.max_force_norm) + 1e-7)
        pair_count_within_cap = bool(int(active_pair_count) <= int(self.max_active_pair_count))
        observed_caps_ready = bool(
            self._policy_caps_ready()
            and energy_within_cap
            and force_within_cap
            and pair_count_within_cap
        )
        return {
            "force_term_policy_caps": self._policy_caps(),
            "force_term_policy_caps_ready": self._policy_caps_ready(),
            "force_term_observed_caps_ready": observed_caps_ready,
            "force_term_bounded_correction_ready": observed_caps_ready,
            "force_term_abs_energy": float(abs_energy),
            "force_term_observed_force_norm": float(force_norm),
            "force_term_max_abs_energy": float(self.max_abs_energy),
            "force_term_max_force_norm": float(self.max_force_norm),
            "force_term_max_active_pair_count": int(self.max_active_pair_count),
            "force_term_abs_energy_within_cap": energy_within_cap,
            "force_term_force_norm_within_cap": force_within_cap,
            "force_term_active_pair_count_within_cap": pair_count_within_cap,
        }

    def _zero_result(
        self,
        state: EngineState,
        coords: torch.Tensor,
        *,
        status: str,
        blocked_reason: str,
        active_pair_count: int = 0,
        abs_energy: float = 0.0,
        force_norm: float = 0.0,
        target_angle_mean: float = 0.0,
    ) -> TermResult:
        zero = torch.zeros(coords.shape[0], dtype=coords.dtype, device=coords.device)
        cap_metadata = self._cap_metadata(
            abs_energy=float(abs_energy),
            force_norm=float(force_norm),
            active_pair_count=int(active_pair_count),
        )
        return TermResult(
            energy=zero,
            forces=torch.zeros_like(coords).detach(),
            diagnostics={
                "term": self.name,
                "status": status,
                "active_pair_count": int(active_pair_count),
                "k_torsion": float(self.k_torsion),
                "target_angle_mean_rad": float(target_angle_mean),
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status=status,
                blocked_reason=blocked_reason,
                extras={
                    "force_term_active_pair_count": int(active_pair_count),
                    "force_term_torsion_quartet_count": int(active_pair_count),
                    "force_term_torsion_target_angle_mean_rad": float(target_angle_mean),
                    "force_term_k_torsion": float(self.k_torsion),
                    **cap_metadata,
                },
            ),
        )

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        del pairs
        coords = state.coords.detach().clone().requires_grad_(True)
        metadata = dict(state.metadata)
        atom_count = int(coords.shape[1])
        quartets = _quartet_tensor(
            _metadata_value(metadata, "torsion_atom_quartets", "torsion_quartets"),
            size=atom_count,
            device=coords.device,
        )
        if quartets is None:
            return self._zero_result(
                state,
                coords,
                status="torsion_quartets_missing",
                blocked_reason="torsion_prior_quartets_missing",
            )

        targets = _target_tensor(
            _metadata_value(
                metadata,
                "torsion_target_angles_rad",
                "torsion_targets_rad",
                "torsion_target_rad",
            ),
            count=int(quartets.shape[0]),
            dtype=coords.dtype,
            device=coords.device,
        )
        if targets is None:
            return self._zero_result(
                state,
                coords,
                status="torsion_targets_invalid",
                blocked_reason="torsion_prior_targets_invalid",
                active_pair_count=int(quartets.shape[0]),
            )

        angles = _dihedral_angles(coords, quartets)
        if not bool(torch.isfinite(angles).all().item()):
            return self._zero_result(
                state,
                coords,
                status="torsion_geometry_invalid",
                blocked_reason="torsion_prior_geometry_invalid",
                active_pair_count=int(quartets.shape[0]),
                target_angle_mean=float(targets.detach().mean().cpu().item()),
            )

        delta = angles - targets.view(1, -1)
        k_torsion = torch.tensor(float(self.k_torsion), dtype=coords.dtype, device=coords.device)
        energy = (k_torsion * (1.0 - torch.cos(delta))).sum(dim=1)
        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        forces = -grad
        active_pair_count = int(quartets.shape[0])
        abs_energy = float(energy.detach().abs().max().cpu().item()) if energy.numel() else 0.0
        force_norm = float(forces.detach().norm(dim=-1).max().cpu().item()) if forces.numel() else 0.0
        target_angle_mean = float(targets.detach().mean().cpu().item()) if targets.numel() else 0.0
        cap_metadata = self._cap_metadata(
            abs_energy=abs_energy,
            force_norm=force_norm,
            active_pair_count=active_pair_count,
        )
        if not cap_metadata["force_term_observed_caps_ready"]:
            return self._zero_result(
                state,
                coords,
                status="policy_cap_exceeded",
                blocked_reason="torsion_prior_policy_cap_exceeded",
                active_pair_count=active_pair_count,
                abs_energy=abs_energy,
                force_norm=force_norm,
                target_angle_mean=target_angle_mean,
            )

        angle_mean = float(angles.detach().mean().cpu().item()) if angles.numel() else 0.0
        return TermResult(
            energy=energy.detach(),
            forces=forces.detach(),
            diagnostics={
                "term": self.name,
                "status": "pass",
                "active_pair_count": active_pair_count,
                "k_torsion": float(self.k_torsion),
                "torsion_angle_mean_rad": angle_mean,
                "target_angle_mean_rad": target_angle_mean,
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_torsion_quartet_count": active_pair_count,
                    "force_term_torsion_angle_mean_rad": angle_mean,
                    "force_term_torsion_target_angle_mean_rad": target_angle_mean,
                    "force_term_k_torsion": float(self.k_torsion),
                    **cap_metadata,
                },
            ),
        )
