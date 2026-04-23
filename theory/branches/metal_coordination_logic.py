import torch
import torch.nn as nn


class MetalCoordinationLogic(nn.Module):
    """
    Lightweight metal-coordination adapter.
    Produces bounded restorative forces around a few high-density pseudo metal centers.
    """

    always_zero_output = False

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.coordination_strength = nn.Parameter(torch.tensor(0.35, device=dev))
        self.preferred_distance = nn.Parameter(torch.tensor(2.25, device=dev))
        self.coordination_cutoff = nn.Parameter(torch.tensor(3.2, device=dev))
        self.max_centers = 2

    def forward(self, c, top, nb_data, pe, sim_params):
        bsz, n_atoms, _ = c.shape
        if n_atoms <= 1:
            f = torch.zeros_like(c, device=self.dev)
            return f, {"mean_force": 0.0, "active_centers": 0}

        if not isinstance(nb_data, (tuple, list)) or len(nb_data) < 3:
            f = torch.zeros_like(c, device=self.dev)
            return f, {"mean_force": 0.0, "active_centers": 0}

        nb_idx, _nb_dist, nb_mask = nb_data
        if nb_idx.numel() == 0:
            f = torch.zeros_like(c, device=self.dev)
            return f, {"mean_force": 0.0, "active_centers": 0}

        k = torch.relu(self.coordination_strength).to(dtype=c.dtype)
        r0 = torch.clamp(self.preferred_distance, min=1.5, max=3.0).to(dtype=c.dtype)
        cutoff = torch.clamp(self.coordination_cutoff, min=2.5, max=4.5).to(dtype=c.dtype)

        safe_idx = nb_idx.clamp_min(0).long()
        batch_idx = torch.arange(bsz, device=c.device).view(bsz, 1, 1).expand_as(safe_idx)
        neigh = c[batch_idx, safe_idx]  # [B, N, K, 3]
        center = c.unsqueeze(2).expand_as(neigh)
        dr = center - neigh
        dist = torch.linalg.norm(dr, dim=-1).clamp_min(1e-8)
        unit = dr / dist.unsqueeze(-1)

        base_mask = (nb_mask > 0.5) & (nb_idx >= 0)
        close_mask = base_mask & (dist <= cutoff)
        density = close_mask.float().sum(dim=-1)  # [B, N]

        n_centers = int(min(self.max_centers, max(1, n_atoms // 32 + 1)))
        center_scores, center_idx = torch.topk(density, k=n_centers, dim=-1)
        center_active = center_scores > 0.0

        center_force = torch.zeros_like(c, device=self.dev)
        ligand_force = torch.zeros_like(c, device=self.dev)
        active_center_count = int(center_active.sum().item())

        atom_i = torch.arange(n_atoms, device=c.device, dtype=torch.long).view(1, n_atoms, 1).expand_as(safe_idx)

        for cslot in range(n_centers):
            picked = center_idx[:, cslot]  # [B]
            picked_mask = center_active[:, cslot].view(bsz, 1, 1)  # [B,1,1]
            is_center = atom_i == picked.view(bsz, 1, 1)
            pair_mask = close_mask & is_center & picked_mask
            if not bool(pair_mask.any().item()):
                continue

            stretch = (dist - r0) * pair_mask.float()
            f_pair = (-k * stretch).unsqueeze(-1) * unit  # [B,N,K,3]
            f_center = f_pair.sum(dim=2)  # [B,N,3]
            center_force = center_force + f_center

            # Ligand-side equal-and-opposite accumulation.
            contrib = (-f_pair).reshape(bsz, -1, 3)
            lig_idx = safe_idx.reshape(bsz, -1)
            ligand_force.scatter_add_(
                1,
                lig_idx.unsqueeze(-1).expand(-1, -1, 3),
                contrib,
            )

        f = center_force + ligand_force
        mean_force = float(torch.linalg.norm(f, dim=-1).mean().item())
        mean_density = float(density.mean().item())
        return f, {
            "mean_force": mean_force,
            "active_centers": active_center_count,
            "mean_local_coordination_count": mean_density,
        }
