# theory/branches/aromatic_logic.py

import torch
import torch.nn as nn

class AromaticLogic(nn.Module):
    """
    Specialist module for aromatic interactions (e.g., pi-pi stacking).
    """
    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.pi_pi_strength = nn.Parameter(torch.tensor(0.2, device=dev))

    def forward(self, c, top, nb_data, pe, sim_params):
        # Calculate aromatic interaction forces
        f_arom = torch.zeros_like(c, device=self.dev)
        info = {'mean_force': f_arom.norm(dim=-1).mean().item()}
        return f_arom, info
