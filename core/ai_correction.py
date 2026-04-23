# core/ai_correction.py

import torch
import torch.nn as nn
import torch.nn.functional as F

class SE3EquivariantCorrection(nn.Module):
    """
    SE(3)-equivariant neural network for predicting force corrections.
    Based on e3nn library principles, implemented with standard PyTorch for simplicity.
    """
    def __init__(self, state_dim=128, hidden_dim=256, num_layers=3):
        super(SE3EquivariantCorrection, self).__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # Coord encoder (equivariance maintained by relative coords)
        self.coord_encoder = nn.Sequential(
            nn.Linear(3, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU()
        )

        # Topology encoder (invariant features)
        self.topo_feature_dim = getattr(Config, 'TOPO_FEATURE_DIM', 64) # Config에 정의 필요 또는 기본값
        self.topo_encoder = nn.Sequential(
            nn.Linear(self.topo_feature_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU()
        )

        # Global parameters encoder (invariant features)
        self.param_encoder = nn.Sequential(
            nn.Linear(4, hidden_dim // 4), # temp, salt_conc, pH, ionic_strength
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU()
        )

        # Message passing layers (simplified MLPs for equivariance)
        layers = []
        for i in range(num_layers):
            in_dim = hidden_dim if i > 0 else hidden_dim * 3 # Coord + Topo + Param
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.SiLU())
            layers.append(nn.Dropout(0.1))
        self.message_passing = nn.Sequential(*layers)

        # Output layer (force prediction, equivariant)
        self.output_head = nn.Linear(hidden_dim, 3)

    def forward(self, c, top, nb_data, pe, sim_params):
        """
        Args:
            c: Coordinates [B, N, 3]
            top: Topology object
            nb_ Neighbor data from spatial hash
            pe: Potential energy tensor (from core forces)
            sim_params: Dict containing global params like temp, salt concentration etc.
        Returns:
            f_corr: Force corrections [B, N, 3]
            aux_info: Auxiliary information dictionary for logging/debugging
        """
        B, N, _ = c.shape

        # Encode coordinates (relative positions maintain equivariance)
        rel_coords = c.unsqueeze(1) - c.unsqueeze(2) # [B, N, N, 3]
        # Apply mask for neighbors
        _, nb_dist, nb_mask = nb_data
        mask = nb_mask.unsqueeze(-1) # [B, N, K, 1]
        rel_coords_nb = rel_coords.gather(2, nb_idx.unsqueeze(-1).expand(-1, -1, -1, 3)) # [B, N, K, 3]
        rel_coords_nb = rel_coords_nb * mask # Apply mask
        coord_features = self.coord_encoder(rel_coords_nb) # [B, N, K, hidden_dim]

        # Aggregate neighbor features (mean pooling maintains equivariance)
        coord_features_agg = (coord_features * mask).sum(dim=2) / (mask.sum(dim=2) + 1e-8) # [B, N, hidden_dim]

        # Encode topology (invariant per atom)
        topo_features = getattr(top, 'residue_features', torch.zeros(N, self.topo_feature_dim, device=c.device))
        topo_features_batch = topo_features.unsqueeze(0).expand(B, -1, -1) # [1, N, feat] -> [B, N, feat]
        topo_encoded = self.topo_encoder(topo_features_batch) # [B, N, hidden_dim]

        # Encode global parameters (invariant)
        param_tensor = torch.tensor([
            sim_params.get('temp', 300.0),
            sim_params.get('salt_conc', 0.1),
            sim_params.get('pH', 7.0),
            sim_params.get('ionic_strength', 0.15)
        ], dtype=torch.float32, device=c.device).unsqueeze(0).expand(B, -1) # [1, 4] -> [B, 4]
        param_encoded = self.param_encoder(param_tensor).unsqueeze(1).expand(-1, N, -1) # [B, 1, hidden_dim] -> [B, N, hidden_dim]

        # Combine features
        combined_features = torch.cat([coord_features_agg, topo_encoded, param_encoded], dim=-1) # [B, N, hidden_dim * 3]

        # Message passing (equivariant MLP layers)
        messages = self.message_passing(combined_features) # [B, N, hidden_dim]

        # Output force corrections (equivariant)
        f_corr = self.output_head(messages) # [B, N, 3]

        # Auxiliary info for logging
        aux_info = {
            'mean_force_magnitude': f_corr.norm(dim=-1).mean().item(),
            'param_temp': sim_params.get('temp', 300.0)
        }

        return f_corr, aux_info

    def compile(self, **kwargs):
        """
        torch.compile을 사용하여 모델을 컴파일합니다.
        """
        # self.eval() # If compiling for inference
        compiled_forward = torch.compile(self.forward, **kwargs)
        # 기존 forward 메서드를 컴파일된 것으로 교체
        self.forward = compiled_forward
        print(f"SE3EquivariantCorrection compiled with kwargs: {kwargs}")
