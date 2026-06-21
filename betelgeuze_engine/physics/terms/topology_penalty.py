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


def _edge_tensor(value: Any, *, size: int, device: torch.device) -> torch.Tensor | None:
    if value is None:
        return None
    try:
        edges = torch.as_tensor(value, dtype=torch.long, device=device).reshape(-1, 2)
    except (TypeError, ValueError, RuntimeError):
        return None
    if int(edges.numel()) == 0:
        return None
    if bool(((edges < 0) | (edges >= int(size))).any().item()):
        return None
    if bool((edges[:, 0] == edges[:, 1]).any().item()):
        return None
    return edges


def _target_distances(
    value: Any,
    *,
    count: int,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor | None:
    if value is None:
        return None
    try:
        targets = torch.as_tensor(value, dtype=dtype, device=device).reshape(-1)
    except (TypeError, ValueError, RuntimeError):
        return None
    if int(targets.numel()) == 1:
        targets = targets.expand(count)
    if (
        int(targets.numel()) != int(count)
        or not bool(torch.isfinite(targets).all().item())
        or bool((targets <= 0.0).any().item())
    ):
        return None
    return targets


@dataclass
class TopologyPenaltyTerm:
    """Guarded topology edge-length prior for product-valid ligand/protein topology."""

    k_topology: float = 0.2
    max_abs_energy: float = 50.0
    max_force_norm: float = 25.0
    max_active_pair_count: int = 4096
    name: str = "topology_penalty"

    def _policy_caps(self) -> dict[str, float]:
        return {
            "max_abs_energy": float(self.max_abs_energy),
            "max_force_norm": float(self.max_force_norm),
            "max_active_pair_count": float(self.max_active_pair_count),
        }

    def _policy_caps_ready(self) -> bool:
        return bool(
            math.isfinite(float(self.k_topology))
            and float(self.k_topology) >= 0.0
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
        target_distance_mean: float = 0.0,
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
                "k_topology": float(self.k_topology),
                "target_distance_mean": float(target_distance_mean),
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status=status,
                blocked_reason=blocked_reason,
                extras={
                    "force_term_active_pair_count": int(active_pair_count),
                    "force_term_topology_edge_count": int(active_pair_count),
                    "force_term_topology_target_distance_mean": float(target_distance_mean),
                    "force_term_k_topology": float(self.k_topology),
                    **cap_metadata,
                },
            ),
        )

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        del pairs
        coords = state.coords.detach().clone().requires_grad_(True)
        metadata = dict(state.metadata)
        topology_fidelity = str(metadata.get("topology_fidelity") or "")
        ligand_topology_valid = metadata.get("ligand_topology_valid") is True
        ligand_claim_safe = metadata.get("ligand_topology_claim_safe", ligand_topology_valid) is True
        if topology_fidelity != "sequence_mapped":
            return self._zero_result(
                state,
                coords,
                status="topology_not_sequence_mapped",
                blocked_reason="topology_penalty_topology_not_sequence_mapped",
            )
        if not ligand_topology_valid or not ligand_claim_safe:
            return self._zero_result(
                state,
                coords,
                status="ligand_topology_invalid",
                blocked_reason="topology_penalty_ligand_topology_invalid",
            )

        atom_count = int(coords.shape[1])
        edges = _edge_tensor(
            _metadata_value(metadata, "topology_edge_indices", "topology_bond_edges"),
            size=atom_count,
            device=coords.device,
        )
        if edges is None:
            return self._zero_result(
                state,
                coords,
                status="topology_edges_missing",
                blocked_reason="topology_penalty_edges_missing",
            )
        targets = _target_distances(
            _metadata_value(
                metadata,
                "topology_edge_target_distances",
                "topology_bond_target_distances",
            ),
            count=int(edges.shape[0]),
            dtype=coords.dtype,
            device=coords.device,
        )
        if targets is None:
            return self._zero_result(
                state,
                coords,
                status="topology_targets_invalid",
                blocked_reason="topology_penalty_targets_invalid",
                active_pair_count=int(edges.shape[0]),
            )

        src = edges[:, 0]
        dst = edges[:, 1]
        distances = (coords[:, src, :] - coords[:, dst, :]).norm(dim=-1).clamp_min(1e-9)
        delta = distances - targets.view(1, -1)
        k_topology = torch.tensor(float(self.k_topology), dtype=coords.dtype, device=coords.device)
        energy = 0.5 * k_topology * delta.pow(2).sum(dim=1)
        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        forces = -grad
        active_pair_count = int(edges.shape[0])
        abs_energy = float(energy.detach().abs().max().cpu().item()) if energy.numel() else 0.0
        force_norm = float(forces.detach().norm(dim=-1).max().cpu().item()) if forces.numel() else 0.0
        target_distance_mean = float(targets.detach().mean().cpu().item()) if targets.numel() else 0.0
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
                blocked_reason="topology_penalty_policy_cap_exceeded",
                active_pair_count=active_pair_count,
                abs_energy=abs_energy,
                force_norm=force_norm,
                target_distance_mean=target_distance_mean,
            )

        distance_mean = float(distances.detach().mean().cpu().item()) if distances.numel() else 0.0
        return TermResult(
            energy=energy.detach(),
            forces=forces.detach(),
            diagnostics={
                "term": self.name,
                "status": "pass",
                "active_pair_count": active_pair_count,
                "k_topology": float(self.k_topology),
                "topology_edge_distance_mean": distance_mean,
                "target_distance_mean": target_distance_mean,
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_topology_edge_count": active_pair_count,
                    "force_term_topology_edge_distance_mean": distance_mean,
                    "force_term_topology_target_distance_mean": target_distance_mean,
                    "force_term_k_topology": float(self.k_topology),
                    **cap_metadata,
                },
            ),
        )
