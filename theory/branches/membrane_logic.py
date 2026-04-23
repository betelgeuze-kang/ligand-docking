import torch
import torch.nn as nn


class MembraneLogic(nn.Module):
    """
    Lightweight membrane adapter with bounded, physically-motivated signals.
    """

    always_zero_output = False

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.hydrophobic_mismatch_penalty = nn.Parameter(torch.tensor(0.24, device=dev))
        self.lipid_tail_interaction = nn.Parameter(torch.tensor(0.18, device=dev))
        self.insertion_k = nn.Parameter(torch.tensor(0.16, device=dev))
        self.membrane_half_thickness_A = nn.Parameter(torch.tensor(14.0, device=dev))

    def _hydrophobic_profile(self, c: torch.Tensor, top) -> torch.Tensor:
        bsz, n_atoms, _ = c.shape
        hydro = None
        if hasattr(top, "hydrophobicity"):
            raw = getattr(top, "hydrophobicity")
            if isinstance(raw, torch.Tensor):
                if raw.dim() == 1:
                    hydro = raw.unsqueeze(0).expand(bsz, -1)
                elif raw.dim() == 2:
                    hydro = raw
        if hydro is None:
            hydro = torch.zeros((bsz, n_atoms), dtype=c.dtype, device=c.device)
            if hasattr(top, "residue_types"):
                rt = getattr(top, "residue_types")
                if isinstance(rt, torch.Tensor):
                    if rt.dim() == 1:
                        rt = rt.unsqueeze(0).expand(bsz, -1)
                    rt = rt.to(device=c.device)
                    # Coarse hydrophobic set (ALA/VAL/ILE/LEU/MET/PHE/TRP/TYR/PRO-like ids).
                    hydro_like = (
                        (rt == 0)
                        | (rt == 4)
                        | (rt == 7)
                        | (rt == 9)
                        | (rt == 10)
                        | (rt == 12)
                        | (rt == 17)
                        | (rt == 18)
                        | (rt == 19)
                    )
                    hydro = hydro_like.float()
        return hydro.to(dtype=c.dtype, device=c.device).clamp(0.0, 1.0)

    def _membrane_frame(self, c: torch.Tensor, sim_params):
        normal_raw = sim_params.get("membrane_normal", [0.0, 0.0, 1.0])
        normal = torch.as_tensor(normal_raw, dtype=c.dtype, device=c.device).reshape(-1)
        if int(normal.numel()) != 3:
            normal = torch.tensor([0.0, 0.0, 1.0], dtype=c.dtype, device=c.device)
        normal = normal / torch.linalg.norm(normal).clamp_min(1e-8)
        z0 = float(sim_params.get("membrane_midplane", 0.0))
        z0_t = torch.tensor(z0, dtype=c.dtype, device=c.device)
        return normal, z0_t

    def _insertion_force(self, c: torch.Tensor, hydro: torch.Tensor, normal: torch.Tensor, z0: torch.Tensor):
        depth = torch.einsum("bni,i->bn", c, normal) - z0
        half = torch.clamp(self.membrane_half_thickness_A, min=8.0, max=22.0).to(dtype=c.dtype)
        desired_depth = torch.where(hydro > 0.5, 0.60 * half, 0.90 * half) * torch.tanh(depth / half.clamp_min(1e-8))
        k_ins = torch.relu(self.insertion_k).to(dtype=c.dtype)
        f_scalar = -k_ins * (depth - desired_depth)
        f_vec = f_scalar.unsqueeze(-1) * normal.view(1, 1, 3)
        return f_vec, depth, half

    def _mismatch_force(self, c: torch.Tensor, depth: torch.Tensor, half: torch.Tensor, normal: torch.Tensor):
        # Penalize persistent hydrophobic mismatch while keeping bounded gradients.
        mismatch = torch.abs(depth) - half
        penalty = torch.tanh(mismatch / half.clamp_min(1e-8))
        sign_depth = torch.sign(depth)
        k_m = torch.relu(self.hydrophobic_mismatch_penalty).to(dtype=c.dtype)
        f_scalar = -k_m * penalty * sign_depth
        return f_scalar.unsqueeze(-1) * normal.view(1, 1, 3), mismatch

    def _lipid_contact_force(self, c: torch.Tensor, nb_data, depth: torch.Tensor, half: torch.Tensor):
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return torch.zeros_like(c, device=self.dev)
        nb_idx, _nb_dist, nb_mask = nb_data
        if nb_idx.numel() == 0:
            return torch.zeros_like(c, device=self.dev)

        bsz, n_atoms, _ = c.shape
        safe_idx = nb_idx.clamp_min(0).long()
        batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
        neigh = c[batch_idx, safe_idx]
        center = c.unsqueeze(2).expand_as(neigh)
        dr = center - neigh
        dist = torch.linalg.norm(dr, dim=-1).clamp_min(1e-8)
        unit = dr / dist.unsqueeze(-1)

        atom_i = torch.arange(n_atoms, device=c.device).view(1, n_atoms, 1).expand_as(safe_idx)
        depth_neigh = depth[batch_idx, safe_idx]
        same_leaflet = (depth.unsqueeze(2) * depth_neigh) >= 0.0
        in_membrane = (torch.abs(depth).unsqueeze(2) <= (half + 2.0)) & (torch.abs(depth_neigh) <= (half + 2.0))
        seq_gap = torch.abs(atom_i - safe_idx)
        mask = (nb_mask > 0.5) & (nb_idx >= 0) & same_leaflet & in_membrane & (seq_gap >= 2)
        window = (1.0 - torch.abs(dist - 5.2) / 3.0).clamp(min=0.0)
        strength = torch.relu(self.lipid_tail_interaction).to(dtype=c.dtype)
        mag = strength * window * mask.float()
        f_pair = -mag.unsqueeze(-1) * unit
        return f_pair.sum(dim=2)

    def forward(self, c, top, nb_data, pe, sim_params):
        hydro = self._hydrophobic_profile(c, top)
        normal, z0 = self._membrane_frame(c, sim_params)
        f_insert, depth, half = self._insertion_force(c, hydro, normal, z0)
        f_mismatch, mismatch = self._mismatch_force(c, depth, half, normal)
        f_contact = self._lipid_contact_force(c, nb_data, depth, half)
        f_membrane = f_insert + f_mismatch + f_contact
        info = {
            "mean_force": float(torch.linalg.norm(f_membrane, dim=-1).mean().item()),
            "mean_insertion_force": float(torch.linalg.norm(f_insert, dim=-1).mean().item()),
            "mean_mismatch_force": float(torch.linalg.norm(f_mismatch, dim=-1).mean().item()),
            "mean_contact_force": float(torch.linalg.norm(f_contact, dim=-1).mean().item()),
            "mean_abs_depth_A": float(torch.abs(depth).mean().item()),
            "mean_hydrophobic_mismatch_A": float(torch.relu(mismatch).mean().item()),
        }
        return f_membrane, info
