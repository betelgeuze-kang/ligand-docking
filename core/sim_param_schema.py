from __future__ import annotations

from typing import Mapping, Optional, Sequence

import torch

CORE_SIM_PARAM_DEFAULTS = {
    "temp": 300.0,
    "salt_conc": 0.1,
    "pH": 7.0,
    "ionic_strength": 0.15,
}

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


class ScalarConditioningError(ValueError):
    """A scalar-only consumer received a heterogeneous batch condition."""


def coerce_sim_param_float(v, default: float) -> float:
    """Convert a scalar condition without averaging different batch values."""

    if torch.is_tensor(v):
        if v.numel() == 0:
            return float(default)
        flat = v.detach().to(dtype=torch.float64, device="cpu").reshape(-1)
        if not bool(torch.isfinite(flat).all().item()):
            raise ScalarConditioningError("runtime parameter contains non-finite values")
        reference = flat[0]
        if not bool(torch.equal(flat, reference.expand_as(flat))):
            raise ScalarConditioningError(
                "scalar runtime consumer requires identical values across the batch"
            )
        return float(reference.item())
    if isinstance(v, (list, tuple)):
        if not v:
            return float(default)
        try:
            flat = torch.as_tensor(v, dtype=torch.float64).reshape(-1)
        except (TypeError, ValueError) as exc:
            raise ScalarConditioningError("runtime parameter must be numeric") from exc
        return coerce_sim_param_float(flat, default)
    try:
        value = float(v)
    except (TypeError, ValueError):
        return float(default)
    if not torch.isfinite(torch.tensor(value, dtype=torch.float64)).item():
        raise ScalarConditioningError("runtime parameter must be finite")
    return value


def vectorize_sim_params(
    sim_params: Optional[Mapping[str, object]],
    *,
    keys: Sequence[str] = DEFAULT_RUNTIME_CONDITIONING_KEYS,
    defaults: Mapping[str, float] = CORE_SIM_PARAM_DEFAULTS,
    device=None,
    dtype=torch.float32,
) -> torch.Tensor:
    """Vectorize conditions for a scalar-only consumer.

    Batched tensors are accepted only when every row is identical. Consumers
    that need per-sample conditions must use the Engine v2 `[B,P]` runtime
    conditioning contract instead.
    """

    params = sim_params if isinstance(sim_params, Mapping) else {}
    values = []
    for key in keys:
        default = float(defaults.get(key, 0.0))
        values.append(coerce_sim_param_float(params.get(key, default), default))
    return torch.tensor(values, dtype=dtype, device=device)
