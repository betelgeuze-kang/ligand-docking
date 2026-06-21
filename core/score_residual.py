"""Compatibility shim for score-level residual correction helpers."""

from __future__ import annotations

from betelgeuze_engine.residual.score import (
    DEFAULT_MAX_ABS_DELTA,
    DEFAULT_YELLOW_BAND,
    PRODUCTION_MODES,
    SCORE_RESIDUAL_CONTRACT,
    SUPPORTED_FAMILIES,
    apply_score_residual,
    residual_band,
)

__all__ = [
    "DEFAULT_MAX_ABS_DELTA",
    "DEFAULT_YELLOW_BAND",
    "PRODUCTION_MODES",
    "SCORE_RESIDUAL_CONTRACT",
    "SUPPORTED_FAMILIES",
    "apply_score_residual",
    "residual_band",
]
