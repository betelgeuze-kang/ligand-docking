"""Score-level residual correction helpers for ranking assistance.

This module is intentionally separate from guarded force residual correction:
it adjusts scalar ranking scores and never claims to apply a physical force
residual.
"""

from __future__ import annotations

from typing import Any

import numpy as np

SCORE_RESIDUAL_CONTRACT = "score_residual_ranking_heuristic_v1"
SUPPORTED_FAMILIES = {"gpcr", "kinase", "ion_channel"}
PRODUCTION_MODES = {"assist", "production", "production_guarded"}
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
    refine_tier_delta: float = 0.0,
    mm_gbsa_delta: float = 0.0,
    refine_confidence: float = 0.0,
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
            "contract": SCORE_RESIDUAL_CONTRACT,
            "residual_scope": "score_ranking_heuristic",
            "physical_force_residual_claim": False,
        }

    refine_signal = 0.12 * float(refine_tier_delta) + 0.10 * float(mm_gbsa_delta)
    refine_signal *= float(np.clip(refine_confidence, 0.0, 1.0))
    raw = (
        0.35 * float(prior_pressure)
        + 0.40 * float(structural_weakness)
        - 0.25 * float(structural_support)
        + 0.20 * float(topo_delta)
        - 0.15 * float(abs(delta_backmap))
        + refine_signal
    )
    gated = raw if (raw > 0.0 and prior_pressure > 0.05) else 0.0
    delta = _clip_delta(gated, max_abs_delta)
    shadow = float(base_score) + float(delta)
    mode_norm = str(mode).lower()
    abstention_reason = ""
    if mode_norm == "shadow_only":
        active = float(base_score)
        status = "residual_shadow_only"
    elif mode_norm == "production_guarded":
        yellow = float(DEFAULT_YELLOW_BAND)
        if float(abs(delta)) <= 0.0:
            active = float(base_score)
            status = "production_guarded_abstained"
            abstention_reason = "zero_delta"
        elif float(abs(delta)) > yellow:
            active = float(base_score)
            status = "production_guarded_abstained"
            abstention_reason = "yellow_band_exceeded"
        else:
            active = float(shadow)
            status = "production_guarded_applied"
    elif mode_norm in PRODUCTION_MODES:
        active = float(shadow)
        status = "residual_ready"
    else:
        active = float(shadow)
        status = "residual_ready"
    return {
        "active_score": float(active),
        "shadow_score": float(shadow),
        "residual_delta": float(delta),
        "residual_delta_raw": float(raw),
        "residual_band": residual_band(abs(float(delta))),
        "status": status,
        "mode": str(mode),
        "family": fam,
        "abstention_reason": abstention_reason,
        "corrected_score": float(shadow),
        "uncertainty": float(abs(delta) / max(float(max_abs_delta), 1e-6)),
        "refine_tier_delta": float(refine_tier_delta),
        "mm_gbsa_delta": float(mm_gbsa_delta),
        "refine_confidence": float(refine_confidence),
        "contract": SCORE_RESIDUAL_CONTRACT,
        "residual_scope": "score_ranking_heuristic",
        "physical_force_residual_claim": False,
    }
