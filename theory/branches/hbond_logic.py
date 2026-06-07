# theory/branches/hbond_logic.py

import torch
import torch.nn as nn

from core.interaction_forces import analytic_hbond_forces


class HbondLogic(nn.Module):
    """Specialist module for hydrogen bond interactions."""

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.hbond_energy = nn.Parameter(torch.tensor(-1.0, device=dev))

    def forward(self, c, top, nb_data, pe, sim_params):
        strength = float(self.hbond_energy.detach().cpu().item())
        f_hbond = analytic_hbond_forces(c, nb_data, strength=strength)
        info = {"mean_force": f_hbond.norm(dim=-1).mean().item()}
        return f_hbond, info
