"""Proxy score → experimental ΔG calibration (claim-safe)."""

from __future__ import annotations

from typing import Any

import numpy as np

CALIBRATION_CLAIM_BOUNDARY = (
    "Linear calibration from supplied reference pairs only. "
    "Does not imply physics-accurate absolute binding affinity."
)


def fit_linear_calibration(
    proxy_values: np.ndarray | list[float],
    reference_dg: np.ndarray | list[float],
) -> dict[str, Any]:
    """Least-squares fit: reference_dg ≈ slope * proxy + intercept."""
    x = np.asarray(proxy_values, dtype=np.float64).reshape(-1)
    y = np.asarray(reference_dg, dtype=np.float64).reshape(-1)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    n = int(x.size)
    if n < 2:
        return {
            "status": "blocked_insufficient_pairs",
            "pair_count": n,
            "slope": 1.0,
            "intercept": 0.0,
            "spearman": None,
            "claim_boundary": CALIBRATION_CLAIM_BOUNDARY,
        }
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    spearman = _spearman(x, y)
    return {
        "status": "calibration_ready",
        "pair_count": n,
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(r2),
        "spearman": spearman,
        "claim_boundary": CALIBRATION_CLAIM_BOUNDARY,
    }


def apply_calibration(proxy_value: float, params: dict[str, Any]) -> float:
    slope = float(params.get("slope", 1.0))
    intercept = float(params.get("intercept", 0.0))
    return float(slope * float(proxy_value) + intercept)


def calibration_quality_gate(params: dict[str, Any], *, min_pairs: int = 5, min_spearman: float = 0.3) -> dict[str, Any]:
    pair_count = int(params.get("pair_count", 0))
    spearman = params.get("spearman")
    ready = pair_count >= int(min_pairs) and spearman is not None and float(spearman) >= float(min_spearman)
    return {
        "calibration_promotion_ready": bool(ready),
        "pair_count": pair_count,
        "spearman": spearman,
        "min_pairs_required": int(min_pairs),
        "min_spearman_required": float(min_spearman),
    }


def _spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    if x.size < 2:
        return None
    rx = _rankdata(x)
    ry = _rankdata(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = float(np.sqrt(np.sum(rx ** 2) * np.sum(ry ** 2)))
    if denom < 1e-12:
        return None
    return float(np.sum(rx * ry) / denom)


def _rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(values) + 1, dtype=np.float64)
    return ranks
