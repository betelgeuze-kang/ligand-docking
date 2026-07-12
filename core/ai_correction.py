# core/ai_correction.py

from __future__ import annotations

from collections.abc import Mapping

import torch
import torch.nn as nn

from core.definitions import Config


def _batch_parameter(
    sim_params: Mapping[str, object],
    key: str,
    default: float,
    *,
    batch_size: int,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    raw = sim_params.get(key, default)
    if isinstance(raw, torch.Tensor):
        value = raw.to(dtype=dtype, device=device)
    else:
        value = torch.as_tensor(raw, dtype=dtype, device=device)
    if value.numel() == 1:
        return value.reshape(1).expand(batch_size)
    if value.ndim == 2 and value.shape[1] == 1:
        value = value[:, 0]
    if value.ndim != 1 or int(value.shape[0]) != int(batch_size):
        raise ValueError(
            f"sim_params[{key!r}] must be scalar, [B], or [B,1]"
        )
    if not bool(torch.isfinite(value).all().item()):
        raise ValueError(f"sim_params[{key!r}] must be finite")
    return value


class NeuralForceCorrection(nn.Module):
    """Frame-dependent legacy neural force correction.

    This is not advertised as SE(3)-equivariant and remains behind product
    fail-closed guards. Runtime conditioning is preserved per sample; the model
    never averages different batch conditions into one scalar.
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
        del pe
        if not isinstance(sim_params, Mapping):
            raise TypeError("sim_params must be a mapping")
        b, n, _ = c.shape
        nb_idx, _nb_dist, nb_mask = nb_data
        safe_idx = nb_idx.clamp_min(0)
        batch_idx = torch.arange(b, device=c.device).view(b, 1, 1).expand(b, n, safe_idx.shape[-1])
        neighbor_pos = c[batch_idx, safe_idx]
        rel_coords_nb = neighbor_pos - c.unsqueeze(2)
        mask = nb_mask.unsqueeze(-1).to(dtype=c.dtype)
        rel_coords_nb = rel_coords_nb * mask
        coord_features = self.coord_encoder(rel_coords_nb)
        coord_features_agg = (coord_features * mask).sum(dim=2) / (mask.sum(dim=2) + 1e-8)

        topo_features = getattr(top, "residue_features", None)
        if topo_features is None:
            topo_features_batch = torch.zeros(
                (b, n, self.topo_feature_dim),
                dtype=c.dtype,
                device=c.device,
            )
        else:
            topo_features = topo_features.to(dtype=c.dtype, device=c.device)
            if topo_features.ndim == 2:
                if tuple(topo_features.shape) != (n, self.topo_feature_dim):
                    raise ValueError("rank-two residue_features must have shape [N,F]")
                topo_features_batch = topo_features.unsqueeze(0).expand(b, -1, -1)
            elif topo_features.ndim == 3:
                if tuple(topo_features.shape) != (b, n, self.topo_feature_dim):
                    raise ValueError("rank-three residue_features must have shape [B,N,F]")
                topo_features_batch = topo_features
            else:
                raise ValueError("residue_features must have shape [N,F] or [B,N,F]")
        topo_encoded = self.topo_encoder(topo_features_batch)

        parameter_columns = (
            _batch_parameter(sim_params, "temp", 300.0, batch_size=b, dtype=c.dtype, device=c.device),
            _batch_parameter(sim_params, "salt_conc", 0.1, batch_size=b, dtype=c.dtype, device=c.device),
            _batch_parameter(sim_params, "pH", 7.0, batch_size=b, dtype=c.dtype, device=c.device),
            _batch_parameter(sim_params, "ionic_strength", 0.15, batch_size=b, dtype=c.dtype, device=c.device),
        )
        param_tensor = torch.stack(parameter_columns, dim=-1)
        param_encoded = self.param_encoder(param_tensor).unsqueeze(1).expand(-1, n, -1)

        combined_features = torch.cat([coord_features_agg, topo_encoded, param_encoded], dim=-1)
        messages = self.message_passing(combined_features)
        f_corr = self.output_head(messages)

        aux_info = {
            "mean_force_magnitude": f_corr.norm(dim=-1).mean().item(),
            "param_temp_by_sample": parameter_columns[0].detach().cpu().tolist(),
            "runtime_conditioning_batch_preserved": True,
            "runtime_conditioning_batch_mean_used": False,
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


SE3EquivariantCorrection = NeuralForceCorrection
