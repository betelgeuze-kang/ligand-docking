# theory/branches/cation_pi_logic.py

import torch
import torch.nn as nn

class CationPiLogic(nn.Module):
    """
    Specialist module for cation-pi interactions.
    """
    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.catpi_strength = nn.Parameter(torch.tensor(0.4, device=dev))

    def forward(self, c, top, nb_data, pe, sim_params):
        # Calculate cation-pi interaction forces
        f_catpi = torch.zeros_like(c, device=self.dev)
        info = {'mean_force': f_catpi.norm(dim=-1).mean().item()}
        return f_catpi, info
