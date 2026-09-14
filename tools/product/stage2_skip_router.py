"""Conservative Stage2 routing from explicit, finite normalized proxy evidence."""

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


def _unit_interval(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and 0.0 <= number <= 1.0 else None


def _evidence_status(row: dict[str, Any]) -> str | None:
    """Honor explicit domain/evidence declarations; do not infer domain validity."""
    for field in ("is_ood", "ood", "out_of_distribution"):
        if field in row:
            marker = str(row[field]).strip().lower()
            if marker in {"true", "1", "1.0"}:
                return "out_of_distribution"
            if marker not in {"false", "0", "0.0"}:
                return "insufficient_or_invalid"
    for field in ("role", "split", "dataset_split"):
        role = str(row.get(field, "")).strip().lower().replace("-", "_").replace(" ", "_")
        if "ood" in role.split("_") or "out_of_distribution" in role:
            return "out_of_distribution"
    for field in ("routing_evidence_status",):
        if field in row:
            status = str(row[field]).strip().lower()
            if status not in {"valid", "sufficient", "in_distribution"}:
                return "out_of_distribution" if status in {"ood", "out_of_distribution"} else "insufficient_or_invalid"
    return None


def route_stage2_candidate(
    *,
    family: str = "",
    affinity_hint: float | None = None,
    onsps_norm: float | None = None,
    prior_rank_proxy: float | None = None,
    mw_norm: float | None = None,
    skip_fraction_target: float | None = None,
    enabled: bool = True,
    is_ood: bool = False,
    routing_evidence_status: str | None = None,
) -> dict[str, Any]:
    """A target adjusts tail eligibility; it is neither a quota nor a batch cap.

    All four normalized inputs must be explicit values in [0, 1]. A zero
    target selects no tail. Disabling the router explicitly retains every row.
    Domain markers can veto a skip; their absence does not establish ID evidence.
    """
    fam = _normalize_family(family)
    target_skip = _unit_interval(
        skip_fraction_target
        if skip_fraction_target is not None
        else FAMILY_SKIP_FRACTION_TARGET.get(fam, FAMILY_SKIP_FRACTION_TARGET["default"])
    )
    rank_pct = _unit_interval(prior_rank_proxy)
    affinity, polar, mass = (_unit_interval(value) for value in (affinity_hint, onsps_norm, mw_norm))
    declarations = {"is_ood": is_ood}
    if routing_evidence_status is not None:
        declarations["routing_evidence_status"] = routing_evidence_status
    status = _evidence_status(declarations)
    route = {
        "stage2_route_decision": "full_stage2_trajectory",
        "stage2_skip_applied": False,
        "stage2_skip_eligible": False,
        "stage2_skip_reason": "full_trajectory_required",
        "stage2_skip_fraction_target": target_skip,
        "stage2_prior_rank_proxy": rank_pct,
        "stage2_route_input_status": "valid",
    }
    if enabled is not True:
        route.update(stage2_skip_reason="router_disabled" if enabled is False else "invalid_router_configuration",
                     stage2_route_input_status="disabled" if enabled is False else "insufficient_or_invalid")
    elif rank_pct is None:
        route.update(stage2_skip_reason="unknown_rank_requires_full_trajectory",
                     stage2_route_input_status="insufficient_or_invalid")
    elif status is not None:
        route.update(stage2_skip_reason=("out_of_distribution_requires_full_trajectory" if status == "out_of_distribution"
                                         else "invalid_routing_evidence_requires_full_trajectory"),
                     stage2_route_input_status=status)
    elif affinity is None or polar is None or mass is None or target_skip is None:
        route.update(stage2_skip_reason="invalid_routing_evidence_requires_full_trajectory",
                     stage2_route_input_status="insufficient_or_invalid")
    else:
        weak_prior = affinity <= 0.05 and rank_pct > 0.25
        low_polar = polar <= 0.02 and mass <= 0.10
        clearly_tail = rank_pct > max(0.20, 1.0 - target_skip)
        if clearly_tail and (weak_prior or low_polar):
            route.update(stage2_route_decision="skip_stage2_inline_score", stage2_skip_applied=True,
                         stage2_skip_eligible=True,
                         stage2_skip_reason="weak_prior_and_tail_rank" if weak_prior else "low_polar_tail_rank")
    return route


def apply_stage2_skip_router(
    rows: list[dict[str, Any]],
    *,
    family: str = "",
    skip_fraction_target: float | None = None,
    max_skip_fraction: float | None = None,
    enabled: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retain unknown evidence; cap skips at floor(row_count * max_skip_fraction).

    The optional hard cap only removes eligible skips, starting with lower tail
    ranks. It never fills a target quota with candidates lacking usable evidence.
    Equal ranks keep input order, and returned rows preserve input order.
    """
    cap = _unit_interval(max_skip_fraction) if max_skip_fraction is not None else None
    if max_skip_fraction is not None and cap is None:
        raise ValueError("max_skip_fraction must be a finite fraction in [0, 1]")
    routed: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        rank = row.get("prior_rank_proxy")
        if rank is None or (isinstance(rank, str) and not rank.strip()):
            rank = row.get("rank_pct")
        status = _evidence_status(row)
        route = route_stage2_candidate(
            family=str(row.get("family", row.get("target_family", family)) or family),
            affinity_hint=row.get("affinity_hint", row.get("ligand_affinity_hint")),
            onsps_norm=row.get("onsps_norm", row.get("ligand_onsps_norm")),
            prior_rank_proxy=rank,
            mw_norm=row.get("mw_norm", row.get("ligand_mw_norm")),
            skip_fraction_target=skip_fraction_target,
            enabled=enabled,
            routing_evidence_status=status,
        )
        updated.update(route)
        routed.append(updated)
    eligible = [i for i, row in enumerate(routed) if row["stage2_skip_eligible"]]
    max_skip_count = math.floor(len(rows) * cap) if cap is not None else None
    if max_skip_count is not None:
        priority = sorted(eligible, key=lambda i: -routed[i]["stage2_prior_rank_proxy"])
        for i in priority[max_skip_count:]:
            routed[i].update(stage2_route_decision="full_stage2_trajectory", stage2_skip_applied=False,
                             stage2_skip_reason="skip_hard_cap_requires_full_trajectory")
    skipped_rows = [row for row in routed if row["stage2_skip_applied"]]
    traj_rows = [row for row in routed if not row["stage2_skip_applied"]]
    summary = {
        "router_enabled": enabled is True,
        "row_count": len(routed),
        "stage2_skip_eligible_count": len(eligible),
        "stage2_skip_count": len(skipped_rows),
        "stage2_full_count": len(traj_rows),
        "stage2_skip_fraction": len(skipped_rows) / max(len(routed), 1),
        "stage2_skip_fraction_target": _unit_interval(skip_fraction_target),
        "stage2_skip_max_fraction": cap,
        "stage2_skip_max_count": max_skip_count,
        "family": _normalize_family(family),
        "skipped_rows": skipped_rows,
        "routed_rows": routed,
    }
    return traj_rows, summary
