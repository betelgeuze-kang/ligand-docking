# theory/branches/stacking_logic.py

import torch
import torch.nn as nn

class StackingLogic(nn.Module):
    """
    Specialist module for stacking interactions (e.g., base stacking in nucleic acids).
    """
    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.stacking_strength = nn.Parameter(torch.tensor(0.25, device=dev))

    def forward(self, c, top, nb_data, pe, sim_params):
        # Calculate stacking interaction forces
        f_stack = torch.zeros_like(c, device=self.dev)
        info = {'mean_force': f_stack.norm(dim=-1).mean().item()}
        return f_stack, info
