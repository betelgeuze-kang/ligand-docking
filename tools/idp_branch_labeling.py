#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


def quantile_thresholds(rows: List[Dict[str, object]]) -> Dict[str, float]:
    def arr(key: str) -> np.ndarray:
        return np.asarray([float(row.get(key, 0.0) or 0.0) for row in rows], dtype=np.float32)

    cp = arr("on_contact_persistence")
    helicity = arr("on_transient_helicity")
    diversity = arr("on_ensemble_diversity")
    aromatic = arr("frac_aromatic")
    net_charge = arr("net_charge_proxy")
    compactness = -0.6 * arr("on_rg_mean") - 0.4 * arr("on_sasa_proxy_mean") + 8.0 * cp
    condensation = 4.5 * cp - 0.22 * diversity - 0.18 * arr("on_rg_mean") - 0.08 * arr("on_sasa_proxy_mean") + 0.9 * aromatic

    def q(v: np.ndarray, level: float) -> float:
        if v.size == 0:
            return 0.0
        return float(np.quantile(v, level))

    return {
        "cp_q50": q(cp, 0.50),
        "cp_q60": q(cp, 0.60),
        "cp_q75": q(cp, 0.75),
        "helicity_q50": q(helicity, 0.50),
        "helicity_q60": q(helicity, 0.60),
        "helicity_q75": q(helicity, 0.75),
        "diversity_q35": q(diversity, 0.35),
        "diversity_q50": q(diversity, 0.50),
        "diversity_q60": q(diversity, 0.60),
        "diversity_q75": q(diversity, 0.75),
        "aromatic_q50": q(aromatic, 0.50),
        "aromatic_q60": q(aromatic, 0.60),
        "charge_abs_q60": q(np.abs(net_charge), 0.60),
        "compactness_q50": q(compactness, 0.50),
        "compactness_q60": q(compactness, 0.60),
        "compactness_q75": q(compactness, 0.75),
        "condensation_q50": q(condensation, 0.50),
        "condensation_q60": q(condensation, 0.60),
        "condensation_q75": q(condensation, 0.75),
    }


def row_rg_percentiles(rows: List[Dict[str, object]]) -> Dict[str, float]:
    values = sorted((float(row.get("on_rg_mean", 0.0)), idx) for idx, row in enumerate(rows))
    out: Dict[str, float] = {}
    denom = max(len(values) - 1, 1)
    for rank, (_value, idx) in enumerate(values):
        out[str(idx)] = float(rank / denom)
    return out


def dynamic_labels(
    row: Dict[str, object],
    rg_percentile: float,
    thresholds: Dict[str, float],
) -> Tuple[str, Dict[str, int], Dict[str, float]]:
    eps = 1e-6

    def ge(a: float, b: float) -> bool:
        return a >= (b - eps)

    def le(a: float, b: float) -> bool:
        return a <= (b + eps)

    cp = float(row.get("on_contact_persistence", 0.0) or 0.0)
    helicity = float(row.get("on_transient_helicity", 0.0) or 0.0)
    diversity = float(row.get("on_ensemble_diversity", 0.0) or 0.0)
    rg_mean = float(row.get("on_rg_mean", 0.0) or 0.0)
    sasa_mean = float(row.get("on_sasa_proxy_mean", 0.0) or 0.0)
    frac_aromatic = float(row.get("frac_aromatic", 0.0) or 0.0)
    net_charge = float(row.get("net_charge_proxy", 0.0) or 0.0)

    compactness_score = -0.6 * rg_mean - 0.4 * sasa_mean + 8.0 * cp
    helicity_score = 1.5 * helicity - 0.1 * diversity
    branch_label = str(row.get("branch_label", "aggregation_prone"))
    if branch_label == "aggregation_prone":
        condensation_score = 0.72 * compactness_score + 3.2 * cp - 0.16 * diversity + 0.45 * frac_aromatic
    elif branch_label == "helix_tad":
        condensation_score = 2.2 * helicity + 1.8 * cp - 0.10 * diversity + 0.20 * frac_aromatic
    else:
        condensation_score = 5.0 * cp - 0.28 * diversity - 0.10 * rg_mean + 0.95 * frac_aromatic

    if ge(helicity, max(thresholds["helicity_q75"], 0.015)) or (
        branch_label == "helix_tad" and ge(helicity, max(thresholds["helicity_q60"], 0.01))
    ):
        dominant_state = "helix_enriched"
    elif (
        ge(condensation_score, thresholds["condensation_q75"])
        or (
            branch_label == "llps_lcd"
            and ge(condensation_score, thresholds["condensation_q50"])
            and le(diversity, max(thresholds["diversity_q75"], 3.6))
            and ge(frac_aromatic, max(thresholds["aromatic_q50"], 0.08))
        )
    ):
        dominant_state = "sticky_condensed"
    elif ge(compactness_score, thresholds["compactness_q50"]) or (le(rg_percentile, 0.5) and ge(cp, thresholds["cp_q50"])):
        dominant_state = "compact_disordered"
    else:
        dominant_state = "expanded_disordered"

    llps_flag = int(
        (
            branch_label == "llps_lcd"
            and ge(frac_aromatic, max(thresholds["aromatic_q50"], 0.08))
            and le(abs(net_charge), max(thresholds["charge_abs_q60"], 0.12))
            and (
                (dominant_state in {"sticky_condensed", "compact_disordered"} and le(diversity, max(thresholds["diversity_q75"], 4.2)))
                or (ge(condensation_score, thresholds["condensation_q50"]) and le(diversity, max(thresholds["diversity_q75"], 4.0)))
            )
        )
        or (
            ge(condensation_score, thresholds["condensation_q75"])
            and le(diversity, max(thresholds["diversity_q60"], 3.2))
            and ge(frac_aromatic, max(thresholds["aromatic_q50"], 0.08))
        )
    )
    aggregation_flag = int(
        (
            branch_label == "aggregation_prone"
            and ge(compactness_score, thresholds["compactness_q60"])
            and le(diversity, max(thresholds["diversity_q50"], 2.0))
        )
        or (
            ge(compactness_score, thresholds["compactness_q75"])
            and le(diversity, max(thresholds["diversity_q35"], 1.6))
            and le(abs(net_charge), max(thresholds["charge_abs_q60"], 0.08))
        )
    )

    return dominant_state, {"aggregation_flag": aggregation_flag, "llps_flag": llps_flag}, {
        "compactness_score": float(compactness_score),
        "helicity_score": float(helicity_score),
        "condensation_score": float(condensation_score),
    }
