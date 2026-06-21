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


def _weights_tensor(value: Any, *, count: int, dtype: torch.dtype, device: torch.device) -> torch.Tensor | None:
    if value is None:
        return None
    try:
        weights = torch.as_tensor(value, dtype=dtype, device=device).reshape(-1)
    except (TypeError, ValueError, RuntimeError):
        return None
    if int(weights.numel()) != int(count):
        return None
    if not bool(torch.isfinite(weights).all().item()):
        return None
    if bool((weights < 0.0).any().item()):
        return None
    return weights


@dataclass
class WaterDisplacementProxyTerm:
    """Guarded proxy water displacement energy for validated ligand/site topology."""

    k_water: float = 0.05
    sigma: float = 1.0
    max_abs_energy: float = 20.0
    max_force_norm: float = 10.0
    max_active_pair_count: int = 4096
    name: str = "water_displacement_proxy"

    def _policy_caps(self) -> dict[str, float]:
        return {
            "max_abs_energy": float(self.max_abs_energy),
            "max_force_norm": float(self.max_force_norm),
            "max_active_pair_count": float(self.max_active_pair_count),
        }

    def _policy_caps_ready(self) -> bool:
        return bool(
            math.isfinite(float(self.k_water))
            and float(self.k_water) > 0.0
            and math.isfinite(float(self.sigma))
            and float(self.sigma) > 0.0
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
        water_site_count: int = 0,
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
                "water_site_count": int(water_site_count),
                "k_water": float(self.k_water),
                "sigma": float(self.sigma),
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
                    "force_term_water_site_count": int(water_site_count),
                    "force_term_k_water": float(self.k_water),
                    "force_term_sigma": float(self.sigma),
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
        water_displacement_model_valid = metadata.get("water_displacement_model_valid") is True

        if topology_fidelity != "sequence_mapped":
            return self._zero_result(
                state,
                coords,
                status="topology_not_sequence_mapped",
                blocked_reason="water_displacement_proxy_topology_not_sequence_mapped",
            )
        if not ligand_topology_valid or not ligand_claim_safe:
            return self._zero_result(
                state,
                coords,
                status="ligand_topology_invalid",
                blocked_reason="water_displacement_proxy_ligand_topology_invalid",
            )
        if not water_displacement_model_valid:
            return self._zero_result(
                state,
                coords,
                status="water_displacement_model_unvalidated",
                blocked_reason="water_displacement_proxy_model_unvalidated",
            )

        atom_count = int(coords.shape[1])
        ligand_indices = _index_tensor(
            _metadata_value(metadata, "ligand_atom_indices"),
            size=atom_count,
            device=coords.device,
        )
        if ligand_indices is None:
            return self._zero_result(
                state,
                coords,
                status="ligand_indices_missing",
                blocked_reason="water_displacement_proxy_ligand_indices_missing",
            )

        water_site_indices = _index_tensor(
            _metadata_value(metadata, "water_displacement_site_indices", "hydration_site_indices"),
            size=atom_count,
            device=coords.device,
        )
        if water_site_indices is None:
            return self._zero_result(
                state,
                coords,
                status="water_site_indices_missing",
                blocked_reason="water_displacement_proxy_site_indices_missing",
                ligand_atom_count=int(ligand_indices.numel()),
            )
        if bool(torch.isin(ligand_indices, water_site_indices).any().item()):
            return self._zero_result(
                state,
                coords,
                status="water_site_indices_invalid",
                blocked_reason="water_displacement_proxy_site_indices_overlap_ligand",
                ligand_atom_count=int(ligand_indices.numel()),
                water_site_count=int(water_site_indices.numel()),
            )

        raw_weights_value = _metadata_value(metadata, "water_displacement_site_weights", "hydration_site_weights")
        water_site_weights = _weights_tensor(
            raw_weights_value,
            count=int(water_site_indices.numel()),
            dtype=coords.dtype,
            device=coords.device,
        )
        if raw_weights_value is not None and water_site_weights is None:
            return self._zero_result(
                state,
                coords,
                status="water_site_weights_invalid",
                blocked_reason="water_displacement_proxy_weights_invalid",
                ligand_atom_count=int(ligand_indices.numel()),
                water_site_count=int(water_site_indices.numel()),
            )

        ligand_coords = coords[:, ligand_indices, :]
        water_coords = coords[:, water_site_indices, :]

        diffs = ligand_coords.unsqueeze(2) - water_coords.unsqueeze(1)
        distances = diffs.norm(dim=-1)
        sigma_tensor = torch.tensor(float(self.sigma), dtype=coords.dtype, device=coords.device)
        k_water = torch.tensor(float(self.k_water), dtype=coords.dtype, device=coords.device)

        gauss = torch.exp(-0.5 * (distances / sigma_tensor).pow(2))

        if water_site_weights is None:
            water_site_weights = torch.ones(int(water_site_indices.numel()), dtype=coords.dtype, device=coords.device)
        weighted = gauss * water_site_weights.view(1, 1, -1)
        energy = -k_water * weighted.sum(dim=(1, 2))

        grad = torch.autograd.grad(energy.sum(), coords, create_graph=False, retain_graph=False)[0]
        forces = -grad

        active_pair_count = int(ligand_indices.numel()) * int(water_site_indices.numel())
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
                blocked_reason="water_displacement_proxy_policy_cap_exceeded",
                active_pair_count=active_pair_count,
                abs_energy=abs_energy,
                force_norm=force_norm,
                ligand_atom_count=int(ligand_indices.numel()),
                water_site_count=int(water_site_indices.numel()),
            )

        return TermResult(
            energy=energy.detach(),
            forces=forces.detach(),
            diagnostics={
                "term": self.name,
                "status": "pass",
                "active_pair_count": active_pair_count,
                "ligand_atom_count": int(ligand_indices.numel()),
                "water_site_count": int(water_site_indices.numel()),
                "k_water": float(self.k_water),
                "sigma": float(self.sigma),
                **cap_metadata,
            },
            claim_metadata=term_claim_metadata(
                state=state,
                term_name=self.name,
                status="pass",
                extras={
                    "force_term_active_pair_count": active_pair_count,
                    "force_term_ligand_atom_count": int(ligand_indices.numel()),
                    "force_term_water_site_count": int(water_site_indices.numel()),
                    "force_term_k_water": float(self.k_water),
                    "force_term_sigma": float(self.sigma),
                    **cap_metadata,
                },
            ),
        )
