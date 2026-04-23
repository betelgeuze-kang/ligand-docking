import torch
import torch.nn as nn


class NucleicAcidLogic(nn.Module):
    """
    Lightweight DNA/RNA interaction adapter.
    Adds sequence-local backbone restoration and nonlocal stacking-like attraction.
    """

    always_zero_output = False

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.base_stacking_strength = nn.Parameter(torch.tensor(0.32, device=dev))
        self.hbond_in_basepair = nn.Parameter(torch.tensor(0.26, device=dev))
        self.backbone_spacing_A = nn.Parameter(torch.tensor(3.8, device=dev))
        self.backbone_k = nn.Parameter(torch.tensor(0.15, device=dev))

    def _sequence_backbone_force(self, c: torch.Tensor) -> torch.Tensor:
        bsz, n_atoms, _ = c.shape
        if n_atoms <= 1:
            return torch.zeros_like(c, device=self.dev)
        dr = c[:, 1:, :] - c[:, :-1, :]
        dist = torch.linalg.norm(dr, dim=-1).clamp_min(1e-8)
        unit = dr / dist.unsqueeze(-1)
        r0 = torch.clamp(self.backbone_spacing_A, min=2.8, max=4.8).to(dtype=c.dtype)
        k = torch.relu(self.backbone_k).to(dtype=c.dtype)
        stretch = dist - r0
        f_pair = -k * stretch.unsqueeze(-1) * unit
        f = torch.zeros_like(c, device=self.dev)
        f[:, :-1, :] = f[:, :-1, :] - f_pair
        f[:, 1:, :] = f[:, 1:, :] + f_pair
        return f

    def _stacking_force(self, c: torch.Tensor, nb_data) -> torch.Tensor:
        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            return torch.zeros_like(c, device=self.dev)
        nb_idx, _nb_dist, nb_mask = nb_data
        bsz, n_atoms, _ = c.shape
        if nb_idx.numel() == 0:
            return torch.zeros_like(c, device=self.dev)

        safe_idx = nb_idx.clamp_min(0).long()
        batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
        neigh = c[batch_idx, safe_idx]
        center = c.unsqueeze(2).expand_as(neigh)
        dr = center - neigh
        dist = torch.linalg.norm(dr, dim=-1).clamp_min(1e-8)
        unit = dr / dist.unsqueeze(-1)

        atom_i = torch.arange(n_atoms, device=c.device, dtype=torch.long).view(1, n_atoms, 1).expand_as(safe_idx)
        seq_gap = torch.abs(safe_idx - atom_i)
        mask = (nb_mask > 0.5) & (nb_idx >= 0)
        mask = mask & (seq_gap >= 2) & (dist >= 3.2) & (dist <= 6.2)
        strength = torch.relu(self.base_stacking_strength).to(dtype=c.dtype)
        hbond_like = torch.relu(self.hbond_in_basepair).to(dtype=c.dtype)
        window = (1.0 - torch.abs(dist - 4.2) / 2.0).clamp(min=0.0)
        pair_mag = (strength + 0.5 * hbond_like) * window * mask.float()
        f_pair = -pair_mag.unsqueeze(-1) * unit
        return f_pair.sum(dim=2)

    def forward(self, c, top, nb_data, pe, sim_params):
        f_backbone = self._sequence_backbone_force(c)
        f_stack = self._stacking_force(c, nb_data)
        f_na = f_backbone + f_stack
        info = {
            "mean_force": float(torch.linalg.norm(f_na, dim=-1).mean().item()),
            "mean_backbone_force": float(torch.linalg.norm(f_backbone, dim=-1).mean().item()),
            "mean_stacking_force": float(torch.linalg.norm(f_stack, dim=-1).mean().item()),
        }
        return f_na, info
