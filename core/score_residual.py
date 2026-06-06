"""Score-level residual correction helpers (O(1) per candidate)."""

from __future__ import annotations

from typing import Any

import numpy as np

SUPPORTED_FAMILIES = {"gpcr", "kinase", "ion_channel"}
DEFAULT_MAX_ABS_DELTA = 1.5
DEFAULT_YELLOW_BAND = 0.75


def _clip_delta(delta: float, max_abs: float) -> float:
    cap = float(max(max_abs, 0.0))
    return float(np.clip(float(delta), -cap, cap))


def residual_band(abs_delta: float, yellow_band: float = DEFAULT_YELLOW_BAND) -> str:
    if abs_delta <= 0.0:
        return "none"
    if abs_delta >= float(yellow_band):
        return "yellow"
    return "green"


def apply_score_residual(
    base_score: float,
    *,
    family: str,
    prior_pressure: float = 0.0,
    structural_weakness: float = 0.0,
    structural_support: float = 0.0,
    topo_delta: float = 0.0,
    delta_backmap: float = 0.0,
    mode: str = "assist",
    max_abs_delta: float = DEFAULT_MAX_ABS_DELTA,
) -> dict[str, Any]:
    fam = str(family or "").strip().lower().replace("-", "_")
    if fam == "ionchannel":
        fam = "ion_channel"
    if fam not in SUPPORTED_FAMILIES:
        return {
            "active_score": float(base_score),
            "shadow_score": float(base_score),
            "residual_delta": 0.0,
            "residual_delta_raw": 0.0,
            "residual_band": "none",
            "status": "unsupported_family",
            "mode": str(mode),
        }

    raw = (
        0.35 * float(prior_pressure)
        + 0.40 * float(structural_weakness)
        - 0.25 * float(structural_support)
        + 0.20 * float(topo_delta)
        - 0.15 * float(abs(delta_backmap))
    )
    gated = raw if (raw > 0.0 and prior_pressure > 0.05) else 0.0
    delta = _clip_delta(gated, max_abs_delta)
    shadow = float(base_score) + float(delta)
    active = float(base_score) if str(mode).lower() == "shadow_only" else float(shadow)
    return {
        "active_score": float(active),
        "shadow_score": float(shadow),
        "residual_delta": float(delta),
        "residual_delta_raw": float(raw),
        "residual_band": residual_band(abs(float(delta))),
        "status": "residual_ready",
        "mode": str(mode),
        "family": fam,
    }
