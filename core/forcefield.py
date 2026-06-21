# core/forcefield.py

import os
from typing import Any, Iterable

import torch
import torch.nn as nn
from .spatial import GridSpatialHash
from .topology import TopologyFactory
from .config import config, logger
from .rust_hip_backend import RustHipBackend
from .sequence_topology import (
    residue_coarse_charges_from_indices,
    residue_nonbonded_params_from_indices,
)
from betelgeuze_engine.contracts import EnergyForces, EngineState
from betelgeuze_engine.physics import ProductForceField, default_force_term_registry
from betelgeuze_engine.physics.neighbor import NeighborPairs


def default_product_forcefield(*, term_names: Iterable[str] | None = None) -> ProductForceField:
    """Return the product engine forcefield while keeping this legacy module import path."""
    return ProductForceField.from_registry(default_force_term_registry(), names=term_names)


class ForceField(nn.Module):
    """
    Physics-based force field calculator using HIP kernels for nonbonded interactions.
    Integrates with AI correction modules.
    Supports Mixed Precision (FP16/FP32).
    """
    def __init__(self, top, params=None, use_mixed_precision=False, neighbor_settings=None, force_backend="auto"):
        super(ForceField, self).__init__()
        self.top = top
        self.params = params or {'d_e': 20.0, 'eps_solv': 25.0, 'sigma': 3.8, 'r0': 4.2}
        # Legacy compatibility: older tests/tools expect `ff` attribute to exist.
        self.ff = self.params
        neighbor_settings = dict(neighbor_settings or {})
        grid_spacing = float(neighbor_settings.pop("grid_spacing", 12.0))
        self.sh = GridSpatialHash(top.box_size, grid_spacing, config.DEVICE, **neighbor_settings)
        self.use_mixed_precision = use_mixed_precision # [NEW] Flag for mixed precision
        self.force_backend = str(force_backend or "auto").lower()
        self.rust_backend = RustHipBackend(device=config.DEVICE)
        self.physics_backend = "rust_hip" if (self.force_backend != "pytorch" and self.rust_backend.enabled) else "pytorch"
        self.require_rust_hip = bool(int(os.environ.get("FORCE_RUST_HIP", "0"))) or bool(
            config.get("rust_hip.require", False)
        )
        if self.force_backend == "pytorch":
            self.require_rust_hip = False
        self._rust_fail_logged = False
        if self.rust_backend.enabled:
            logger.info(
                f"ForceField backend=rust_hip kernel={self.rust_backend.status.kernel_name} "
                f"module={self.rust_backend.status.module_path}"
            )
        else:
            if self.require_rust_hip:
                raise RuntimeError(
                    f"Rust HIP backend is required but unavailable: {self.rust_backend.status.reason}"
                )
            logger.warning(
                f"ForceField backend=pytorch (Rust HIP disabled: {self.rust_backend.status.reason})"
            )
        self._rust_nb_cache = None
        self._rust_nb_ref_coords = None
        self._rust_nb_shape = None
        self._rust_nb_call_counter = 0
        self._rust_nb_last_displacement_check = -1

    def _engine_atom_types_for_coords(
        self,
        coords: torch.Tensor,
        atom_types: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if atom_types is not None:
            out = atom_types.to(device=coords.device, dtype=torch.long).reshape(-1)
            if int(out.shape[0]) != int(coords.shape[1]):
                raise ValueError("atom_types length must match coords N")
            return out
        residue_types = None
        if hasattr(self.top, "residue_types_for_coordinate_count"):
            residue_types = self.top.residue_types_for_coordinate_count(int(coords.shape[1]))
        if residue_types is not None:
            return residue_types.to(device=coords.device, dtype=torch.long).reshape(-1)
        return torch.zeros(int(coords.shape[1]), dtype=torch.long, device=coords.device)

    def _engine_metadata_for_coords(
        self,
        coords: torch.Tensor,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        top_claim = getattr(self.top, "claim_metadata", None)
        if isinstance(top_claim, dict):
            out.update(dict(top_claim))
        fidelity = str(out.get("topology_fidelity") or "placeholder_alanine")
        out.setdefault("ligand_topology_valid", False)
        out.setdefault("hbond_evidence_status", "not_assessed")
        out.setdefault("force_residual_applied", False)
        out.setdefault("claim_safe", False)
        out.setdefault(
            "blocked_reason",
            "" if out.get("claim_safe") is True else (
                "placeholder_alanine_topology"
                if fidelity != "sequence_mapped"
                else "core_forcefield_bridge_claim_not_promoted"
            ),
        )
        if "hbond_roles" not in out and hasattr(self.top, "hbond_roles"):
            roles = list(self.top.hbond_roles())
            if len(roles) == int(coords.shape[1]):
                out["hbond_roles"] = roles
        if metadata:
            out.update(dict(metadata))
        return out

    def engine_state(
        self,
        coords: torch.Tensor,
        *,
        atom_types: torch.Tensor | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EngineState:
        """Build the product-engine state from this legacy topology without changing compute()."""
        if coords.ndim != 3 or coords.shape[-1] != 3:
            raise ValueError("coords must have shape [B, N, 3]")
        return EngineState(
            coords=coords,
            atom_types=self._engine_atom_types_for_coords(coords, atom_types),
            residue_types=getattr(self.top, "residue_types", None),
            box=getattr(self.top, "box_size", None),
            metadata=self._engine_metadata_for_coords(coords, metadata),
        )

    def product_energy_forces(
        self,
        coords: torch.Tensor,
        pairs: NeighborPairs | None = None,
        *,
        atom_types: torch.Tensor | None = None,
        metadata: dict[str, Any] | None = None,
        claim_metadata: dict[str, Any] | None = None,
        term_names: Iterable[str] | None = None,
        product_neighbor_required: bool = True,
    ) -> EnergyForces:
        """Compatibility bridge to betelgeuze_engine ProductForceField with claim metadata."""
        state = self.engine_state(coords, atom_types=atom_types, metadata=metadata)
        product_forcefield = default_product_forcefield(term_names=term_names)
        return product_forcefield.energy_forces(
            state,
            pairs,
            claim_metadata=claim_metadata,
            product_neighbor_required=product_neighbor_required,
        )

    def _minimum_image(self, dr, box):
        return dr - box * torch.floor(dr / box + 0.5)

    def _rust_neighbor_needs_rebuild(self, coords_model):
        self._rust_nb_call_counter += 1
        if self._rust_nb_cache is None or self._rust_nb_ref_coords is None or self._rust_nb_shape is None:
            return True
        if tuple(coords_model.shape) != tuple(self._rust_nb_shape):
            return True
        if coords_model.device != self._rust_nb_ref_coords.device:
            return True
        if self.sh.skin <= 0.0:
            return True
        if (self._rust_nb_call_counter - self._rust_nb_last_displacement_check) < self.sh.rebuild_stride:
            return False

        self._rust_nb_last_displacement_check = self._rust_nb_call_counter
        box = self.top.box_size.to(device=coords_model.device, dtype=coords_model.dtype).view(1, 1, 3)
        disp = self._minimum_image(coords_model - self._rust_nb_ref_coords, box)
        max_disp = disp.norm(dim=-1).amax()
        return bool(max_disp.item() >= (0.5 * self.sh.skin))

    def _get_or_build_rust_neighbor(self, coords_model, runtime_params):
        if self.rust_backend.has_neighbor_builder():
            if self._rust_neighbor_needs_rebuild(coords_model):
                self._rust_nb_cache = self.rust_backend.build_neighbor_list(
                    coords_model.float(),
                    box_size=runtime_params["box_size"],
                    cutoff=float(self.sh.list_cutoff),
                    max_neighbors=int(self.sh.max_neighbors),
                    grid_dims=self.sh.grid_dims,
                    max_atoms_per_cell=int(self.sh.max_atoms_per_cell),
                )
                self._rust_nb_ref_coords = coords_model.detach().clone()
                self._rust_nb_shape = tuple(coords_model.shape)
                self._rust_nb_last_displacement_check = self._rust_nb_call_counter
            return self._rust_nb_cache
        return self.sh.get_neighbor_data(coords_model)

    def _residue_forcefield_params_for_coords(
        self,
        n_atoms: int,
        *,
        device: torch.device,
        dtype: torch.dtype,
        base_sigma: float,
        base_epsilon: float,
        charge_scale: float,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None:
        if not hasattr(self.top, "residue_types_for_coordinate_count"):
            return None
        residue_types = self.top.residue_types_for_coordinate_count(int(n_atoms))
        if residue_types is None:
            return None
        residue_types = residue_types.to(device=device)
        sigma, epsilon = residue_nonbonded_params_from_indices(
            residue_types,
            base_sigma=float(base_sigma),
            base_epsilon=float(base_epsilon),
        )
        charges = residue_coarse_charges_from_indices(
            residue_types,
            charge_scale=float(charge_scale),
        )
        return (
            sigma.to(device=device, dtype=dtype),
            epsilon.to(device=device, dtype=dtype),
            charges.to(device=device, dtype=dtype),
        )

    def _compute_coarse_backbone_bonds(self, c: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Restricted fast-tier CA backbone harmonic bonds over consecutive residues."""
        B, N, _ = c.shape
        f_bond = torch.zeros_like(c)
        pe_bond = torch.zeros(B, 1, dtype=c.dtype, device=c.device)
        n_ca = int(getattr(self.top, "n_res", N))
        if n_ca < 2 or N < n_ca:
            return f_bond, pe_bond
        k = float(self.params.get("backbone_bond_k", 1.5))
        if k <= 0.0:
            return f_bond, pe_bond
        r0 = float(self.params.get("backbone_bond_r0", 3.8))
        ca = c[:, :n_ca, :]
        dr = ca[:, :-1, :] - ca[:, 1:, :]
        box = self.top.box_size.to(dtype=c.dtype, device=c.device).view(1, 1, 3)
        dr = dr - box * torch.floor(dr / box + 0.5)
        eps = torch.tensor(1e-8, dtype=c.dtype, device=c.device)
        r = dr.norm(dim=-1).clamp_min(eps)
        delta = r - torch.tensor(r0, dtype=c.dtype, device=c.device)
        k_t = torch.tensor(k, dtype=c.dtype, device=c.device)
        pair_force = -k_t * delta.unsqueeze(-1) * dr / r.unsqueeze(-1)
        f_bond[:, : n_ca - 1, :] += pair_force
        f_bond[:, 1:n_ca, :] -= pair_force
        pe_bond = 0.5 * k_t * delta.pow(2).sum(dim=-1, keepdim=True)
        return f_bond, pe_bond

    def _compute_coarse_backbone_angles(self, c: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Restricted fast-tier CA angle restraint over consecutive residue triplets."""
        B, N, _ = c.shape
        f_angle = torch.zeros_like(c)
        pe_zero = torch.zeros(B, 1, dtype=c.dtype, device=c.device)
        n_ca = int(getattr(self.top, "n_res", N))
        if n_ca < 3 or N < n_ca:
            return f_angle, pe_zero
        k = float(self.params.get("backbone_angle_k", 0.0))
        if k <= 0.0:
            return f_angle, pe_zero
        theta0 = float(self.params.get("backbone_angle_theta0_rad", 2.0))
        ca = c[:, :n_ca, :].detach().clone().requires_grad_(True)
        box = self.top.box_size.to(dtype=c.dtype, device=c.device).view(1, 1, 3)
        v1 = ca[:, :-2, :] - ca[:, 1:-1, :]
        v2 = ca[:, 2:, :] - ca[:, 1:-1, :]
        v1 = v1 - box * torch.floor(v1 / box + 0.5)
        v2 = v2 - box * torch.floor(v2 / box + 0.5)
        eps = torch.tensor(1e-8, dtype=c.dtype, device=c.device)
        cos_theta = (v1 * v2).sum(dim=-1) / (v1.norm(dim=-1).clamp_min(eps) * v2.norm(dim=-1).clamp_min(eps))
        theta = torch.acos(cos_theta.clamp(-0.999999, 0.999999))
        delta = theta - torch.tensor(theta0, dtype=c.dtype, device=c.device)
        k_t = torch.tensor(k, dtype=c.dtype, device=c.device)
        pe_angle = 0.5 * k_t * delta.pow(2).sum(dim=-1, keepdim=True)
        grad = torch.autograd.grad(pe_angle.sum(), ca, create_graph=False, retain_graph=False)[0]
        f_angle[:, :n_ca, :] = -grad.detach()
        return f_angle, pe_angle.detach()

    def compute(self, c, nb_data):
        """
        Computes forces and potential energy using HIP kernels and AI correction.
        Supports Mixed Precision (FP16/FP32).
        Args:
            c: Coordinates [B, N, 3]
            nb_ Neighbor data from spatial hash
        Returns:
            f: Forces [B, N, 3]
            pe: Potential energy [B, 1]
        """
        B, N_input, _ = c.shape
        device = c.device

        # [NEW] Cast coordinates to FP16 if mixed precision is enabled
        coords_input = c.half() if self.use_mixed_precision else c.float()
        coords_model = coords_input
        project_virtual_to_ca = False
        n_ca = self.top.n_res

        # CA-only 입력이면 virtual SC를 만들어 내부적으로 CA+SC 2-bead로 물리 계산한다.
        if self.top.use_virtual_sc and N_input == n_ca:
            c_sc = self._compute_virtual_sc_coords(self.top, coords_input)
            coords_model = torch.cat([coords_input, c_sc], dim=1)
            project_virtual_to_ca = True

        # --- 1. Core Physics Calculation (via HIP) ---
        if self.physics_backend == "rust_hip" and self.rust_backend.enabled:
            try:
                runtime_params = dict(self.params)
                if "box_size" not in runtime_params:
                    runtime_params["box_size"] = float(self.top.box_size[0].item())
                runtime_params.setdefault("cutoff", float(self.sh.list_cutoff))
                runtime_params.setdefault("grid_x", int(self.sh.grid_dims[0].item()))
                runtime_params.setdefault("grid_y", int(self.sh.grid_dims[1].item()))
                runtime_params.setdefault("grid_z", int(self.sh.grid_dims[2].item()))
                runtime_params.setdefault("max_atoms_per_cell", int(self.sh.max_atoms_per_cell))
                nb_model = None
                if self.rust_backend.needs_neighbor_list():
                    if nb_data is None or nb_data[0].shape[1] != coords_model.shape[1]:
                        nb_model = self._get_or_build_rust_neighbor(coords_model, runtime_params)
                    else:
                        nb_model = nb_data
                f_core_model, pe = self.rust_backend.compute_nonbonded(coords_model.float(), nb_model, runtime_params)
                f_bond_model, pe_bond = self._compute_coarse_backbone_bonds(coords_model.float())
                f_angle_model, pe_angle = self._compute_coarse_backbone_angles(coords_model.float())
                f_core_model = f_core_model + f_bond_model + f_angle_model
                pe = pe + pe_bond + pe_angle
                if project_virtual_to_ca:
                    f_core = f_core_model[:, :n_ca, :] + f_core_model[:, n_ca:(2 * n_ca), :]
                else:
                    f_core = f_core_model
                return f_core, pe
            except Exception as e:
                if self.require_rust_hip:
                    raise RuntimeError(f"Rust HIP compute failed in required mode: {e}") from e
                if not self._rust_fail_logged:
                    logger.warning(f"HIP force calculation failed: {e}. Falling back to PyTorch.")
                    self._rust_fail_logged = True

        # Fallback: Use a standard PyTorch implementation for nonbonded forces if HIP is not available or fails.
        nb_model = nb_data
        if nb_model is None or nb_model[0].shape[1] != coords_model.shape[1]:
            nb_model = self.sh.get_neighbor_data(coords_model)
        f_core_model, pe = self._compute_nonbonded_pytorch(coords_model, nb_model, to_fp32=True)
        f_bond_model, pe_bond = self._compute_coarse_backbone_bonds(coords_model.float())
        f_angle_model, pe_angle = self._compute_coarse_backbone_angles(coords_model.float())
        f_core_model = f_core_model + f_bond_model + f_angle_model
        pe = pe + pe_bond + pe_angle
        if project_virtual_to_ca:
            f_core = f_core_model[:, :n_ca, :] + f_core_model[:, n_ca:(2 * n_ca), :]
        else:
            f_core = f_core_model

        # --- 2. AI Correction Application ---
        # This part remains largely the same, but now f_core comes from HIP (potentially FP32)
        # The orchestrator (which includes AI correction) is called separately in the main loop
        # So, ForceField.compute returns the *core* forces, and AI correction is applied elsewhere

        return f_core, pe

    def _compute_nonbonded_pytorch(self, c, nb_data, to_fp32=False):
        """
        Fallback PyTorch implementation for nonbonded forces.
        Can operate in FP16 and cast result to FP32.
        """
        # This is a simplified version. Real implementation would be in HIP kernel.
        B, N, _ = c.shape
        device = c.device

        # Calculate distances for neighbors only (from nb_data)
        nb_idx, nb_dist, nb_mask = nb_data

        sigma = self.params['sigma']
        eps = self.params['eps_solv']
        dtype = c.dtype
        sigma_t = torch.tensor(sigma, dtype=dtype, device=device)
        eps_t = torch.tensor(eps, dtype=dtype, device=device)
        eps_small = torch.tensor(1e-8, dtype=dtype, device=device)
        electrostatic_scale = torch.tensor(
            float(self.params.get("electrostatic_scale", 4.0)),
            dtype=dtype,
            device=device,
        )
        debye_kappa = torch.tensor(
            float(self.params.get("debye_kappa", 0.125)),
            dtype=dtype,
            device=device,
        )
        residue_params = self._residue_forcefield_params_for_coords(
            N,
            device=device,
            dtype=dtype,
            base_sigma=float(sigma),
            base_epsilon=float(eps),
            charge_scale=float(self.params.get("residue_charge_scale", 1.0)),
        )

        # Gather neighbor coordinates with mask
        K = nb_idx.shape[-1]
        safe_idx = nb_idx.clamp_min(0)
        batch_idx = torch.arange(B, device=device).view(B, 1, 1).expand(B, N, K)
        neigh_coords = c[batch_idx, safe_idx] # [B, N, K, 3]
        center_coords = c.unsqueeze(2).expand(-1, -1, K, -1) # [B, N, K, 3]

        dr = center_coords - neigh_coords
        box = self.top.box_size.to(dtype=dtype, device=device).view(1, 1, 1, 3)
        dr -= box * torch.floor(dr / box + 0.5)

        mask_bool = nb_mask.bool() & (nb_idx >= 0)
        dr = torch.where(mask_bool.unsqueeze(-1), dr, torch.zeros_like(dr))
        # HIP 커널의 MIN_R2=4.0 정책과 정합되도록 최소 유효 거리 2.0 Å를 적용
        r = dr.norm(dim=-1).clamp_min(2.0) # [B, N, K]
        r = torch.where(mask_bool, r, torch.ones_like(r))
        mask = mask_bool.to(dtype)

        if residue_params is None:
            sigma_pair = sigma_t
            eps_pair = eps_t
            charge_pair = torch.zeros_like(r)
        else:
            sigma_atom, eps_atom, charge_atom = residue_params
            sigma_center = sigma_atom.view(1, N, 1)
            eps_center = eps_atom.view(1, N, 1)
            charge_center = charge_atom.view(1, N, 1)
            sigma_neigh = sigma_atom[safe_idx]
            eps_neigh = eps_atom[safe_idx]
            charge_neigh = charge_atom[safe_idx]
            sigma_pair = 0.5 * (sigma_center + sigma_neigh)
            eps_pair = torch.sqrt((eps_center * eps_neigh).clamp_min(0.0))
            charge_pair = charge_center * charge_neigh

        r_sigma_inv = sigma_pair / (r + eps_small)
        r_sigma_inv_6 = r_sigma_inv.pow(6)
        r_sigma_inv_12 = r_sigma_inv_6.pow(2)

        lj_pot = 4 * eps_pair * (r_sigma_inv_12 - r_sigma_inv_6)
        lj_force_mag = 4 * eps_pair * (12 * r_sigma_inv_12 - 6 * r_sigma_inv_6) / (r + eps_small)
        screened = torch.exp(-debye_kappa * r)
        coulomb_pot = electrostatic_scale * charge_pair * screened / (r + eps_small)
        coulomb_force_mag = (
            electrostatic_scale
            * charge_pair
            * screened
            * (debye_kappa * r + 1.0)
            / ((r + eps_small).pow(2))
        )

        total_pot_masked = (lj_pot + coulomb_pot) * mask
        total_force_mag = lj_force_mag + coulomb_force_mag
        f_pair = total_force_mag.unsqueeze(-1) * dr / (r.unsqueeze(-1) + eps_small)
        f_pair = f_pair * mask.unsqueeze(-1)

        # Neighbor list는 (i->j, j->i)를 포함하므로 energy는 0.5 배로 보정
        pe = 0.5 * total_pot_masked.sum(dim=-1).sum(dim=-1, keepdim=True) # [B, 1]
        f_total = f_pair.sum(dim=2) # [B, N, 3]

        # [NEW] Cast result to FP32 if requested
        if to_fp32 and f_total.dtype != torch.float32:
            f_total = f_total.float()
        if to_fp32 and pe.dtype != torch.float32:
            pe = pe.float()

        return f_total, pe

    def compute_reference_pytorch(self, c, cutoff=14.0, max_neighbors=160, skin=0.0):
        """
        High-fidelity PyTorch reference force for residual learning targets.
        """
        n_input = c.shape[1]
        coords_input = c.float()
        coords_model = coords_input
        project_virtual_to_ca = False
        n_ca = self.top.n_res

        if self.top.use_virtual_sc and n_input == n_ca:
            c_sc = self._compute_virtual_sc_coords(self.top, coords_input)
            coords_model = torch.cat([coords_input, c_sc], dim=1)
            project_virtual_to_ca = True

        sh_ref = GridSpatialHash(
            self.top.box_size,
            float(cutoff),
            coords_model.device,
            cutoff=float(cutoff),
            max_neighbors=int(max_neighbors),
            skin=float(skin),
            rebuild_stride=1,
        )
        nb_ref = sh_ref.get_neighbor_data(coords_model, force_rebuild=True)
        f_ref_model, pe_ref = self._compute_nonbonded_pytorch(coords_model, nb_ref, to_fp32=True)
        f_bond_model, pe_bond = self._compute_coarse_backbone_bonds(coords_model.float())
        f_angle_model, pe_angle = self._compute_coarse_backbone_angles(coords_model.float())
        f_ref_model = f_ref_model + f_bond_model + f_angle_model
        pe_ref = pe_ref + pe_bond + pe_angle

        if project_virtual_to_ca:
            f_ref = f_ref_model[:, :n_ca, :] + f_ref_model[:, n_ca:(2 * n_ca), :]
        else:
            f_ref = f_ref_model
        return f_ref, pe_ref

    def _compute_virtual_sc_coords(self, top, c_ca):
        """
        Computes virtual side chain coordinates based on CA coordinates.
        Used for CA-SC 2-bead model.
        """
        if not top.use_virtual_sc:
            return torch.empty(0, 0, 3, device=c_ca.device)

        if hasattr(top, "compute_virtual_sc_coords"):
            return top.compute_virtual_sc_coords(c_ca)

        # Fallback for legacy topology objects without helper method.
        offset = torch.tensor([0.0, 1.5, 0.0], dtype=c_ca.dtype, device=c_ca.device).view(1, 1, 3)
        return c_ca + offset.expand(c_ca.shape[0], c_ca.shape[1], 3)
