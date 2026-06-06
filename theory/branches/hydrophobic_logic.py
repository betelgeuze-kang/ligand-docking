# theory/branches/hydrophobic_logic.py

import torch
import torch.nn as nn

from core.interaction_forces import analytic_hydrophobic_forces


class HydrophobicLogic(nn.Module):
    """Specialist module for hydrophobic interactions."""

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.hydrophobic_strength = nn.Parameter(torch.tensor(0.3, device=dev))

    def forward(self, c, top, nb_data, pe, sim_params):
        strength = float(self.hydrophobic_strength.detach().cpu().item())
        f_hydro = analytic_hydrophobic_forces(c, nb_data, strength=strength)
        info = {"mean_force": f_hydro.norm(dim=-1).mean().item()}
        return f_hydro, info
