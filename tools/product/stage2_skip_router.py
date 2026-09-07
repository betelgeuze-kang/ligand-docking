"""Stage2 routing: missing evidence never implies a low-value candidate."""
from __future__ import annotations

import math
from numbers import Real
from typing import Any

FAMILY_SKIP_FRACTION_TARGET = {
    "gpcr": 0.60, "ion_channel": 0.55, "kinase": 0.56, "default": 0.55,
}


def _normalize_family(family: str) -> str:
    fam = str(family or "").strip().lower().replace("-", "_")
    if fam in {"ionchannel", "ion_trpv1", "trpv1"}:
        return "ion_channel"
    if fam in {"kinase_protease", "protease"}:
        return "kinase"
    return fam or "default"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (Real, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def route_stage2_candidate(
    *, family: str = "", affinity_hint: float = 0.0, onsps_norm: float = 0.0,
    prior_rank_proxy: float | None = None, mw_norm: float = 0.0,
    skip_fraction_target: float | None = None,
) -> dict[str, Any]:
    fam = _normalize_family(family)
    target_skip = _number(skip_fraction_target if skip_fraction_target is not None
                          else FAMILY_SKIP_FRACTION_TARGET.get(fam, FAMILY_SKIP_FRACTION_TARGET["default"]))
    if target_skip is None or not 0. <= target_skip <= 1.:
        raise ValueError("skip_fraction_target must be finite and in [0, 1]")
    rank = _number(prior_rank_proxy)
    affinity, polar, mw = _number(affinity_hint), _number(onsps_norm), _number(mw_norm)
    valid_rank = rank is not None and 0. <= rank <= 1.
    valid_hints = affinity is not None and polar is not None and mw is not None
    if not valid_rank or not valid_hints:
        return {
            "stage2_route_decision": "full_stage2_trajectory", "stage2_skip_applied": False,
            "stage2_skip_reason": "missing_or_invalid_rank" if not valid_rank else "invalid_routing_hint",
            "stage2_skip_fraction_target": target_skip,
            "stage2_prior_rank_proxy": rank if valid_rank else None,
        }
    weak_prior = affinity <= 0.05 and rank > 0.25
    low_polar = polar <= 0.02 and mw <= 0.10
    clearly_tail = rank > max(0.20, 1.0 - target_skip)
    skip = bool(weak_prior or (low_polar and clearly_tail))
    return {
        "stage2_route_decision": "skip_stage2_inline_score" if skip else "full_stage2_trajectory",
        "stage2_skip_applied": skip,
        "stage2_skip_reason": ("weak_prior_and_tail_rank" if weak_prior and clearly_tail
                               else "weak_prior" if weak_prior
                               else "low_polar_tail_rank" if skip else "full_trajectory_required"),
        "stage2_skip_fraction_target": target_skip, "stage2_prior_rank_proxy": rank,
    }


def apply_stage2_skip_router(rows: list[dict[str, Any]], *, family: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    routed: list[dict[str, Any]] = []
    for row in rows:
        rank = row.get("prior_rank_proxy")
        if rank is None or (isinstance(rank, str) and not rank.strip()):
            rank = row.get("rank_pct")
        # Do not silently replace an explicitly corrupt primary rank with an alias.
        route = route_stage2_candidate(
            family=str(row.get("family", row.get("target_family", family)) or family),
            affinity_hint=row.get("affinity_hint", row.get("ligand_affinity_hint", 0.0)),
            onsps_norm=row.get("onsps_norm", row.get("ligand_onsps_norm", 0.0)),
            prior_rank_proxy=rank, mw_norm=row.get("mw_norm", 0.0),
        )
        routed.append({**row, **route})
    skipped = [row for row in routed if row["stage2_skip_applied"]]
    retained = [row for row in routed if not row["stage2_skip_applied"]]
    return retained, {
        "router_enabled": True, "row_count": len(routed), "stage2_skip_count": len(skipped),
        "stage2_full_count": len(retained), "stage2_skip_fraction": len(skipped) / max(len(routed), 1),
        "family": _normalize_family(family), "skipped_rows": skipped, "routed_rows": routed,
    }
