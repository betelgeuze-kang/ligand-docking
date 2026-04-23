# core/forcefield.py

import os
import torch
import torch.nn as nn
from .spatial import GridSpatialHash
from .topology import TopologyFactory
from .config import config, logger
from .rust_hip_backend import RustHipBackend

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

        r_sigma_inv = sigma_t / (r + eps_small)
        r_sigma_inv_6 = r_sigma_inv.pow(6)
        r_sigma_inv_12 = r_sigma_inv_6.pow(2)

        lj_pot = 4 * eps_t * (r_sigma_inv_12 - r_sigma_inv_6)
        lj_force_mag = 4 * eps_t * (12 * r_sigma_inv_12 - 6 * r_sigma_inv_6) / (r + eps_small)

        lj_pot_masked = lj_pot * mask
        f_pair = lj_force_mag.unsqueeze(-1) * dr / (r.unsqueeze(-1) + eps_small)
        f_pair = f_pair * mask.unsqueeze(-1)

        # Neighbor list는 (i->j, j->i)를 포함하므로 energy는 0.5 배로 보정
        pe = 0.5 * lj_pot_masked.sum(dim=-1).sum(dim=-1, keepdim=True) # [B, 1]
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
