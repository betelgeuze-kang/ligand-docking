"""Compatibility shim for topology score correction helpers."""

from __future__ import annotations

from betelgeuze_engine.topology.correction import (
    DEFAULT_MAX_ABS_DELTA_SCORE,
    TOPOLOGY_CORRECTION_CONTRACT,
    build_topo_feature_vector,
    summarize_topo_correction,
    topo_correction_delta,
)

__all__ = [
    "DEFAULT_MAX_ABS_DELTA_SCORE",
    "TOPOLOGY_CORRECTION_CONTRACT",
    "build_topo_feature_vector",
    "summarize_topo_correction",
    "topo_correction_delta",
]
