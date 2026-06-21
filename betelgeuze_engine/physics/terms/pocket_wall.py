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


def _index_tensor(value: Any, *, size: int, device: torch.device) -> torch.Tensor | None:
    if value is None:
        return None
    try:
        indices = torch.as_tensor(value, dtype=torch.long, device=device).reshape(-1)
    except (TypeError, ValueError, RuntimeError):
        return None
    if int(indices.numel()) == 0:
        return None
    if bool(((indices < 0) | (indices >= int(size))).any().item()):
        return None
    return indices


@dataclass
class PocketWallTerm:
    """Guarded harmonic wall that keeps ligand beads within a validated pocket."""

    k_wall: float = 0.2
    default_radius: float | None = None
    max_abs_energy: float = 50.0
    max_force_norm: float = 25.0
    max_active_pair_count: int = 4096
    name: str = "pocket_wall"

    def _policy_caps(self) -> dict[str, float]:
        return {
            "max_abs_energy": float(self.max_abs_energy),
            "max_force_norm": float(self.max_force_norm),
            "max_active_pair_count": float(self.max_active_pair_count),
        }

    def _policy_caps_ready(self) -> bool:
        return bool(
            math.isfinite(float(self.k_wall))
            and float(self.k_wall) > 0.0
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
        ligand_atom_count: int = 0,
        pocket_anchor_count: int = 0,
        radius: float = 0.0,
    ) -> TermResult:
        zero = torch.zeros(coords.shape[0], dtype=coords.dtype, device=coords.device)
        cap_metadata = self._cap_metadata(
            abs_energy=float(abs_energy),
            force_norm=float(force_norm),
            active_pair_count=int(active_pair_count),
        )
        return TermResult(
            energy=zero,
            forces=torch.zeros_like(coords),
            diagnostics={
                "term": self.name,
                "status": status,
                "active_pair_count": int(active_pair_count),
                "ligand_atom_count": int(ligand_atom_count),
                "pocket_anchor_count": int(pocket_anchor_count),
                "pocket_radius": float(radius),
                "k_wall": float(self.k_wall),
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status=status,
                blocked_reason=blocked_reason,
                extras={
                    "force_term_active_pair_count": int(active_pair_count),
                    "force_term_ligand_atom_count": int(ligand_atom_count),
                    "force_term_pocket_anchor_count": int(pocket_anchor_count),
                    "force_term_pocket_radius": float(radius),
                    "force_term_k_wall": float(self.k_wall),
                    **cap_metadata,
                },
            ),
        )

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        del pairs
        coords = state.coords.detach().clone().requires_grad_(True)
        metadata = dict(state.metadata)
        atom_count = int(coords.shape[1])
        ligand_indices = _index_tensor(
            _metadata_value(metadata, "ligand_atom_indices", "ligand_indices"),
            size=atom_count,
            device=coords.device,
        )
        if ligand_indices is None:
            return self._zero_result(
                state,
                coords,
                status="ligand_indices_missing",
                blocked_reason="pocket_wall_ligand_indices_missing",
            )

        radius_value = _metadata_value(metadata, "pocket_radius", "pocket_radius_a")
        if radius_value is None:
            radius_value = self.default_radius
        try:
            radius = float(radius_value)
        except (TypeError, ValueError):
            radius = float("nan")
        if not math.isfinite(radius) or radius <= 0.0:
            return self._zero_result(
                state,
                coords,
                status="pocket_radius_missing",
                blocked_reason="pocket_wall_radius_missing",
                ligand_atom_count=int(ligand_indices.numel()),
            )

        pocket_anchor_indices = _index_tensor(
            _metadata_value(metadata, "pocket_atom_indices", "pocket_anchor_indices"),
            size=atom_count,
            device=coords.device,
        )
        explicit_center_value = _metadata_value(metadata, "pocket_center", "pocket_center_xyz")
        if pocket_anchor_indices is not None:
            center = coords[:, pocket_anchor_indices, :].mean(dim=1)
            pocket_anchor_count = int(pocket_anchor_indices.numel())
            center_source = "pocket_atom_indices"
        elif explicit_center_value is not None:
            try:
                center = torch.as_tensor(
                    explicit_center_value,
                    dtype=coords.dtype,
                    device=coords.device,
                ).reshape(1, 3)
            except (TypeError, ValueError, RuntimeError):
                center = torch.empty(0, dtype=coords.dtype, device=coords.device)
            if center.shape != (1, 3) or not bool(torch.isfinite(center).all().item()):
                return self._zero_result(
                    state,
                    coords,
                    status="pocket_center_invalid",
                    blocked_reason="pocket_wall_center_invalid",
                    ligand_atom_count=int(ligand_indices.numel()),
                    radius=radius,
                )
            center = center.expand(coords.shape[0], 3)
            pocket_anchor_count = 0
            center_source = "pocket_center"
        else:
            return self._zero_result(
                state,
                coords,
                status="pocket_center_missing",
                blocked_reason="pocket_wall_center_missing",
                ligand_atom_count=int(ligand_indices.numel()),
                radius=radius,
            )

        ligand_centroid = coords[:, ligand_indices, :].mean(dim=1)
        dvec = ligand_centroid - center
        distance = dvec.norm(dim=-1)
        radius_tensor = torch.tensor(radius, dtype=coords.dtype, device=coords.device)
        k_wall = torch.tensor(float(self.k_wall), dtype=coords.dtype, device=coords.device)
        excess = torch.relu(distance - radius_tensor)
        energy = 0.5 * k_wall * excess.pow(2)
        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        forces = -grad
        active_pair_count = int(ligand_indices.numel()) * max(int(pocket_anchor_count), 1)
        abs_energy = float(energy.detach().abs().max().cpu().item()) if energy.numel() else 0.0
        force_norm = float(forces.detach().norm(dim=-1).max().cpu().item()) if forces.numel() else 0.0
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
                blocked_reason="pocket_wall_policy_cap_exceeded",
                active_pair_count=active_pair_count,
                abs_energy=abs_energy,
                force_norm=force_norm,
                ligand_atom_count=int(ligand_indices.numel()),
                pocket_anchor_count=pocket_anchor_count,
                radius=radius,
            )
        return TermResult(
            energy=energy.detach(),
            forces=forces.detach(),
            diagnostics={
                "term": self.name,
                "status": "pass",
                "active_pair_count": active_pair_count,
                "ligand_atom_count": int(ligand_indices.numel()),
                "pocket_anchor_count": pocket_anchor_count,
                "pocket_radius": radius,
                "pocket_center_source": center_source,
                "pocket_escape": bool((excess > 0.0).any().item()),
                "pocket_distance_max": float(distance.detach().max().cpu().item()),
                "k_wall": float(self.k_wall),
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_ligand_atom_count": int(ligand_indices.numel()),
                    "force_term_pocket_anchor_count": pocket_anchor_count,
                    "force_term_pocket_radius": radius,
                    "force_term_pocket_center_source": center_source,
                    "force_term_pocket_escape": bool((excess > 0.0).any().item()),
                    "force_term_pocket_distance_max": float(distance.detach().max().cpu().item()),
                    "force_term_k_wall": float(self.k_wall),
                    **cap_metadata,
                },
            ),
        )
