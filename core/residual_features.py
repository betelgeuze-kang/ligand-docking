"""Feature vector assembly for score-residual (refine-tier aware)."""

from __future__ import annotations

from typing import Any

import numpy as np

FEATURE_NAMES = (
    "base_score",
    "prior_pressure",
    "structural_weakness",
    "structural_support",
    "topo_delta",
    "delta_backmap",
    "refine_tier_delta",
    "mm_gbsa_delta",
    "refine_confidence",
    "contact_fraction",
    "clash_count_norm",
)


def build_residual_feature_vector(
    *,
    base_score: float = 0.0,
    prior_pressure: float = 0.0,
    structural_weakness: float = 0.0,
    structural_support: float = 0.0,
    topo_delta: float = 0.0,
    delta_backmap: float = 0.0,
    refine_tier_delta: float = 0.0,
    mm_gbsa_delta: float = 0.0,
    refine_confidence: float = 0.0,
    contact_fraction: float = 0.0,
    clash_count: float = 0.0,
) -> dict[str, Any]:
    clash_norm = float(np.clip(float(clash_count) / 10.0, 0.0, 1.0))
    values = np.asarray(
        [
            float(base_score),
            float(prior_pressure),
            float(structural_weakness),
            float(structural_support),
            float(topo_delta),
            float(delta_backmap),
            float(refine_tier_delta),
            float(mm_gbsa_delta),
            float(refine_confidence),
            float(contact_fraction),
            clash_norm,
        ],
        dtype=np.float32,
    )
    return {
        "feature_names": list(FEATURE_NAMES),
        "feature_vector": values.tolist(),
        "feature_dim": int(values.size),
        "refine_tier_present": bool(abs(refine_tier_delta) > 1e-6 or abs(mm_gbsa_delta) > 1e-6),
    }


def features_from_scoring_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build residual features from a scoring/backmapping result row."""
    base_proxy = float(row.get("binding_energy_mmpbsa_kcal_mol_proxy", row.get("base_score", 0.0)) or 0.0)
    refined = row.get("binding_energy_explicit_water_recheck_kcal_mol_proxy")
    refined_val = float(refined) if refined not in {None, ""} else base_proxy
    mm_gbsa = row.get("deltaG_mm_gbsa_kcal_mol", refined_val)
    mm_gbsa_val = float(mm_gbsa) if mm_gbsa not in {None, ""} else refined_val
    return build_residual_feature_vector(
        base_score=float(row.get("binding_score_composite_v7", base_proxy) or base_proxy),
        prior_pressure=float(row.get("prior_pressure", 0.0) or 0.0),
        structural_weakness=float(row.get("structural_weakness", 0.0) or 0.0),
        structural_support=float(row.get("structural_support", 0.0) or 0.0),
        topo_delta=float(row.get("topo_delta", 0.0) or 0.0),
        delta_backmap=float(row.get("delta_backmap", row.get("onsps_backmap_delta", 0.0)) or 0.0),
        refine_tier_delta=float(refined_val - base_proxy),
        mm_gbsa_delta=float(mm_gbsa_val - base_proxy),
        refine_confidence=float(row.get("physics_refinement_confidence", row.get("refine_confidence", 0.0)) or 0.0),
        contact_fraction=float(row.get("contact_fraction", 0.0) or 0.0),
        clash_count=float(row.get("clash_count", 0.0) or 0.0),
    )
