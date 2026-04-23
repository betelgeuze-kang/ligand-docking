from __future__ import annotations

from typing import Mapping, Optional, Sequence

import torch

CORE_SIM_PARAM_DEFAULTS = {
    "temp": 300.0,
    "salt_conc": 0.1,
    "pH": 7.0,
    "ionic_strength": 0.15,
}

# Runtime conditioning vars are explicitly allow-listed to avoid label leakage.
DEFAULT_RUNTIME_CONDITIONING_KEYS = (
    "temp",
    "salt_conc",
    "pH",
    "ionic_strength",
    "ptm_count",
    "force_scale",
    "cooling_rate",
    "hydro_strength",
    "k_angle",
    "theta0",
    "k_dihedral",
    "phi0_alpha",
    "ai_correction_active",
)

# Fields below are treated as labels/evaluation targets and must never enter runtime conditioning.
LEAKAGE_BLOCKED_SIM_KEYS = (
    "energy",
    "Rg",
    "compactness",
    "sasa",
    "cluster_max",
    "is_llps",
    "is_folded",
    "rmsd",
    "violations",
)


def coerce_sim_param_float(v, default: float) -> float:
    if torch.is_tensor(v):
        if v.numel() == 0:
            return float(default)
        return float(v.float().mean().item())
    try:
        return float(v)
    except Exception:
        return float(default)


def vectorize_sim_params(
    sim_params: Optional[Mapping[str, object]],
    *,
    keys: Sequence[str] = DEFAULT_RUNTIME_CONDITIONING_KEYS,
    defaults: Mapping[str, float] = CORE_SIM_PARAM_DEFAULTS,
    device=None,
    dtype=torch.float32,
) -> torch.Tensor:
    params = sim_params if isinstance(sim_params, Mapping) else {}
    values = []
    for key in keys:
        default = float(defaults.get(key, 0.0))
        values.append(coerce_sim_param_float(params.get(key, default), default))
    return torch.tensor(values, dtype=dtype, device=device)
