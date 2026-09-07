"""Stage2 skip router for top-K cascade throughput (P3)."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

FAMILY_SKIP_FRACTION_TARGET = {
    "gpcr": 0.60,
    "ion_channel": 0.55,
    "kinase": 0.56,
    "default": 0.55,
}


def _normalize_family(family: str) -> str:
    fam = str(family or "").strip().lower().replace("-", "_")
    if fam in {"ionchannel", "ion_trpv1", "trpv1"}:
        return "ion_channel"
    if fam in {"kinase_protease", "protease"}:
        return "kinase"
    return fam or "default"


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (Real, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def route_stage2_candidate(
    *,
    family: str = "",
    affinity_hint: float = 0.0,
    onsps_norm: float = 0.0,
    prior_rank_proxy: float | None = None,
    mw_norm: float = 0.0,
    skip_fraction_target: float | None = None,
) -> dict[str, Any]:
    """Skip only from finite, explicit routing evidence, never an unknown rank."""
    fam = _normalize_family(family)
    target_skip = _finite_number(
        skip_fraction_target
        if skip_fraction_target is not None
        else FAMILY_SKIP_FRACTION_TARGET.get(fam, FAMILY_SKIP_FRACTION_TARGET["default"])
    )
    rank_pct = _finite_number(prior_rank_proxy)
    if rank_pct is not None and not 0.0 <= rank_pct <= 1.0:
        rank_pct = None
    affinity, polar, mass = (_finite_number(value) for value in (affinity_hint, onsps_norm, mw_norm))
    usable = (rank_pct is not None and affinity is not None and polar is not None
              and mass is not None and target_skip is not None and 0.0 <= target_skip <= 1.0)
    if not usable:
        return {
            "stage2_route_decision": "full_stage2_trajectory",
            "stage2_skip_applied": False,
            "stage2_skip_reason": (
                "unknown_rank_requires_full_trajectory" if rank_pct is None
                else "invalid_routing_evidence_requires_full_trajectory"
            ),
            "stage2_skip_fraction_target": target_skip,
            "stage2_prior_rank_proxy": rank_pct,
            "stage2_route_input_status": "insufficient_or_invalid",
        }
    weak_prior = affinity <= 0.05 and rank_pct > 0.25
    low_polar = polar <= 0.02 and mass <= 0.10
    clearly_tail = rank_pct > max(0.20, 1.0 - target_skip)
    skip = bool(weak_prior or (low_polar and clearly_tail))
    decision = "skip_stage2_inline_score" if skip else "full_stage2_trajectory"
    return {
        "stage2_route_decision": decision,
        "stage2_skip_applied": bool(skip),
        "stage2_skip_reason": (
            "weak_prior_and_tail_rank"
            if weak_prior and clearly_tail
            else "low_polar_tail_rank"
            if skip
            else "full_trajectory_required"
        ),
        "stage2_skip_fraction_target": float(target_skip),
        "stage2_prior_rank_proxy": float(rank_pct),
        "stage2_route_input_status": "valid",
    }


def apply_stage2_skip_router(rows: list[dict[str, Any]], *, family: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Annotate rows without mutating input; unknown evidence retains a candidate."""
    routed: list[dict[str, Any]] = []
    skip_count = 0
    for row in rows:
        updated = dict(row)
        rank = row.get("prior_rank_proxy")
        if rank is None or (isinstance(rank, str) and not rank.strip()):
            rank = row.get("rank_pct")
        route = route_stage2_candidate(
            family=str(row.get("family", row.get("target_family", family)) or family),
            affinity_hint=row.get("affinity_hint", row.get("ligand_affinity_hint", 0.0)),
            onsps_norm=row.get("onsps_norm", row.get("ligand_onsps_norm", 0.0)),
            prior_rank_proxy=rank,
            mw_norm=row.get("mw_norm", 0.0),
        )
        updated.update(route)
        routed.append(updated)
        if route["stage2_skip_applied"]:
            skip_count += 1
    skipped_rows = [row for row in routed if row.get("stage2_skip_applied")]
    traj_rows = [row for row in routed if not row.get("stage2_skip_applied")]
    summary = {
        "router_enabled": True,
        "row_count": len(routed),
        "stage2_skip_count": int(skip_count),
        "stage2_full_count": int(len(traj_rows)),
        "stage2_skip_fraction": float(skip_count / max(len(routed), 1)),
        "family": _normalize_family(family),
        "skipped_rows": skipped_rows,
        "routed_rows": routed,
    }
    return traj_rows, summary
