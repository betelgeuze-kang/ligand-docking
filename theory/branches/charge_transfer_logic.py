# theory/branches/charge_transfer_logic.py

import torch
import torch.nn as nn

class ChargeTransferLogic(nn.Module):
    """
    Specialist module for charge transfer interactions.
    """
    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.ct_strength = nn.Parameter(torch.tensor(0.1, device=dev))

    def forward(self, c, top, nb_data, pe, sim_params):
        # Calculate charge transfer forces
        f_ct = torch.zeros_like(c, device=self.dev)
        info = {'mean_force': f_ct.norm(dim=-1).mean().item()}
        return f_ct, info
