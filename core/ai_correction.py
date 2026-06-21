# core/ai_correction.py

import torch
import torch.nn as nn

from core.definitions import Config


class NeuralForceCorrection(nn.Module):
    """
    Frame-dependent neural network for predicting force corrections.

    This module is intentionally not advertised as SE(3)-equivariant. It is a
    legacy MLP correction surface and must stay behind product fail-closed
    guards unless a separate equivariance audit validates a stronger claim.
    """

    def __init__(self, state_dim=128, hidden_dim=256, num_layers=3):
        super().__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.coord_encoder = nn.Sequential(
            nn.Linear(3, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU(),
        )

        self.topo_feature_dim = int(getattr(Config, "TOPO_FEATURE_DIM", 64))
        self.topo_encoder = nn.Sequential(
            nn.Linear(self.topo_feature_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU(),
        )

        self.param_encoder = nn.Sequential(
            nn.Linear(4, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU(),
        )

        layers = []
        for i in range(num_layers):
            in_dim = hidden_dim if i > 0 else hidden_dim * 3
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.SiLU())
            layers.append(nn.Dropout(0.1))
        self.message_passing = nn.Sequential(*layers)
        self.output_head = nn.Linear(hidden_dim, 3)

    def forward(self, c, top, nb_data, pe, sim_params):
        b, n, _ = c.shape
        nb_idx, _nb_dist, nb_mask = nb_data
        batch_idx = torch.arange(b, device=c.device).view(b, 1, 1).expand(b, n, nb_idx.shape[-1])
        neighbor_pos = c[batch_idx, nb_idx]
        rel_coords_nb = neighbor_pos - c.unsqueeze(2)
        mask = nb_mask.unsqueeze(-1)
        rel_coords_nb = rel_coords_nb * mask
        coord_features = self.coord_encoder(rel_coords_nb)

        coord_features_agg = (coord_features * mask).sum(dim=2) / (mask.sum(dim=2) + 1e-8)

        topo_features = getattr(
            top,
            "residue_features",
            torch.zeros(n, self.topo_feature_dim, device=c.device),
        )
        topo_features_batch = topo_features.unsqueeze(0).expand(b, -1, -1)
        topo_encoded = self.topo_encoder(topo_features_batch)

        param_tensor = torch.tensor(
            [
                sim_params.get("temp", 300.0),
                sim_params.get("salt_conc", 0.1),
                sim_params.get("pH", 7.0),
                sim_params.get("ionic_strength", 0.15),
            ],
            dtype=torch.float32,
            device=c.device,
        ).unsqueeze(0).expand(b, -1)
        param_encoded = self.param_encoder(param_tensor).unsqueeze(1).expand(-1, n, -1)

        combined_features = torch.cat([coord_features_agg, topo_encoded, param_encoded], dim=-1)
        messages = self.message_passing(combined_features)
        f_corr = self.output_head(messages)

        aux_info = {
            "mean_force_magnitude": f_corr.norm(dim=-1).mean().item(),
            "param_temp": sim_params.get("temp", 300.0),
            "correction_model_class": self.__class__.__name__,
            "se3_equivariant": False,
            "claim_grade": "frame_dependent_neural_force_correction",
        }
        return f_corr, aux_info

    def claim_metadata(self) -> dict[str, object]:
        return {
            "correction_model_class": self.__class__.__name__,
            "se3_equivariant": False,
            "claim_grade": "frame_dependent_neural_force_correction",
            "claim_safe": False,
            "blocked_reason": "neural_force_correction_not_product_claim_promoted",
        }


# Backward-compatible import alias for legacy tests and callers. Do not use this
# name for product claims; the implementation is not an SE(3)-equivariant model.
SE3EquivariantCorrection = NeuralForceCorrection
