"""PocketMD Lite contract: top-k pocket-local refinement with uncertainty bands.

This closes the Betelgeuze cascade:

    cheap O(N) global screening
        -> H-Bond BackMap (ONSPS-4) interpretable rescoring
        -> top-k pocket-local micro-refinement (PocketMD Lite)

PocketMD Lite never refines the whole library; only the top-k candidates get the
expensive ligand+sidechain local-min / short micro-MD pass. Each refined
candidate is graded into an uncertainty band (green / yellow / red) or made to
**abstain** when refinement evidence is missing. It is fail-closed: a green
(claim-safe) refinement requires local-min survival, H-bond and contact
persistence, and no residual clash; anything missing abstains rather than
guessing.

The refinement itself (local-min, micro-MD) runs under numpy/OpenMM/GPU/CI. This
module is the dependency-free **selection + grading + governance** layer over the
per-candidate refinement evidence, so it is unit-testable in isolation.
"""

from __future__ import annotations

from typing import Any

POCKETMD_LITE_SCHEMA_VERSION = "pocketmd_lite_contract_v1"

# Top-k selection: only the cheapest-to-trust fraction gets the expensive
# refinement, keeping the cascade affordable.
TOPK_DEFAULT_THRESHOLD_PCT = 0.05

# Claim-safe refinement thresholds (defaults; align with repo evidence).
LOCAL_MIN_SURVIVAL_RMSD_A = 2.0  # ligand RMSD after restrained local-min must stay within this
HBOND_PERSISTENCE_MIN = 0.5  # fraction of micro-MD frames retaining the H-bond
CONTACT_PERSISTENCE_MIN = 0.5  # fraction of micro-MD frames retaining key contacts
MAX_CLASH_COUNT = 0  # no residual clash after relief for a green band

# Uncertainty bands.
BAND_GREEN = "green"  # claim-safe refinement
BAND_YELLOW = "yellow"  # survived but borderline; review
BAND_RED = "red"  # refinement failed (local-min did not survive)
BAND_ABSTAIN = "abstain"  # required refinement evidence missing
BAND_COARSE_ONLY = "coarse_only"  # not selected for refinement

CLAIM_BOUNDARY = (
    "PocketMD Lite grades top-k pocket-local refinement evidence into uncertainty bands. A green (claim-safe) "
    "band requires local-min survival (ligand RMSD within threshold), H-bond and contact persistence at or above "
    "threshold, baseline/final clash counts for clash-relief reporting, and no residual clash. Missing evidence "
    "abstains; failed survival is red. It is not all-atom MD, not a binding-affinity claim, and refines only "
    "selected top-k candidates. The uncertainty score is a governance/evidence-completeness posture, not a "
    "calibrated probability. The refinement computation runs elsewhere; this layer selects, grades, and governs."
)


class PocketMdLiteError(ValueError):
    """Raised when a candidate row is malformed."""


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise PocketMdLiteError(f"non-numeric value: {value!r}") from exc


def is_refine_selected(
    *,
    family: str = "",
    rank_pct: float | None = None,
    top_k_threshold_pct: float = TOPK_DEFAULT_THRESHOLD_PCT,
) -> bool:
    """Decide whether a candidate enters the expensive refinement lane."""

    if rank_pct is None:
        return False
    return float(rank_pct) <= float(top_k_threshold_pct)


def _evidence_completeness(values: list[Any]) -> float:
    if not values:
        return 0.0
    present = sum(1 for value in values if value is not None and value != "")
    return round(present / len(values), 6)


def _uncertainty_posture(
    *,
    band: str,
    evidence_completeness: float,
    ligand_rmsd: float | None,
    hbond: float | None,
    contact: float | None,
    clash_count: int | None,
    thresholds: dict[str, Any],
    review_flags: list[str],
) -> tuple[float | None, str]:
    if band == BAND_COARSE_ONLY:
        return None, "coarse_only_not_refined"
    if band == BAND_ABSTAIN:
        return 1.0, "missing_refinement_evidence_high_uncertainty"
    if band == BAND_RED:
        return 1.0, "local_min_failed_high_uncertainty"
    if band == BAND_YELLOW:
        score = min(0.95, 0.6 + 0.05 * len(review_flags) + 0.2 * (1.0 - evidence_completeness))
        return round(score, 6), "yellow_review_uncertainty"
    if band == BAND_GREEN:
        local_threshold = float(thresholds["local_min_survival_rmsd_a"])
        hbond_threshold = float(thresholds["hbond_persistence_min"])
        contact_threshold = float(thresholds["contact_persistence_min"])
        local_pressure = 0.0 if ligand_rmsd is None else min(1.0, max(0.0, ligand_rmsd / local_threshold))
        hbond_pressure = 0.0 if hbond is None else min(1.0, max(0.0, hbond_threshold / max(hbond, 1.0e-12)))
        contact_pressure = (
            0.0 if contact is None else min(1.0, max(0.0, contact_threshold / max(contact, 1.0e-12)))
        )
        clash_pressure = 1.0 if (clash_count or 0) > int(thresholds["max_clash_count"]) else 0.0
        score = 0.35 * max(local_pressure, hbond_pressure, contact_pressure, clash_pressure)
        return round(score, 6), "green_low_uncertainty"
    return 1.0, "unknown_band_high_uncertainty"


def build_pocketmd_lite_assessment(
    candidate: dict[str, Any],
    *,
    top_k_threshold_pct: float = TOPK_DEFAULT_THRESHOLD_PCT,
    local_min_survival_rmsd_a: float = LOCAL_MIN_SURVIVAL_RMSD_A,
    hbond_persistence_min: float = HBOND_PERSISTENCE_MIN,
    contact_persistence_min: float = CONTACT_PERSISTENCE_MIN,
    max_clash_count: int = MAX_CLASH_COUNT,
) -> dict[str, Any]:
    """Grade one candidate's refinement evidence into an uncertainty band."""

    if "entry_id" not in candidate:
        raise PocketMdLiteError("candidate missing required field: entry_id")

    entry_id = str(candidate["entry_id"])
    family = str(candidate.get("family", ""))
    rank_pct = _num(candidate.get("rank_pct"))

    if "selected_for_refine" in candidate:
        selected = bool(candidate["selected_for_refine"])
    else:
        selected = is_refine_selected(family=family, rank_pct=rank_pct, top_k_threshold_pct=top_k_threshold_pct)

    ligand_rmsd = _num(candidate.get("local_min_ligand_rmsd_a"))
    hbond = _num(candidate.get("hbond_persistence"))
    contact = _num(candidate.get("contact_persistence"))
    initial_clash = candidate.get("initial_clash_count", candidate.get("pre_refine_clash_count"))
    initial_clash_count = None if initial_clash in (None, "") else int(initial_clash)
    clash = candidate.get("clash_count")
    clash_count = None if clash in (None, "") else int(clash)
    missing_evidence_fields = [
        field
        for field, value in (
            ("local_min_ligand_rmsd_a", ligand_rmsd),
            ("hbond_persistence", hbond),
            ("contact_persistence", contact),
            ("initial_clash_count", initial_clash_count),
            ("clash_count", clash_count),
        )
        if value is None
    ]
    evidence_completeness = _evidence_completeness([ligand_rmsd, hbond, contact, initial_clash_count, clash_count])
    clash_relief_count = (
        None
        if initial_clash_count is None or clash_count is None
        else int(initial_clash_count - clash_count)
    )
    clash_relief_observed = None if clash_relief_count is None else bool(clash_relief_count > 0)

    reason_code = ""
    review_flags: list[str] = []

    if not selected:
        band = BAND_COARSE_ONLY
        reason_code = "not_selected_for_refine"
        local_min_survived = None
    elif (
        ligand_rmsd is None
        or hbond is None
        or contact is None
        or initial_clash_count is None
        or clash_count is None
    ):
        band = BAND_ABSTAIN
        reason_code = "missing_refinement_evidence"
        local_min_survived = None
    else:
        local_min_survived = ligand_rmsd <= local_min_survival_rmsd_a
        if not local_min_survived:
            band = BAND_RED
            reason_code = "local_min_did_not_survive"
        else:
            if clash_count > max_clash_count:
                review_flags.append("residual_clash")
            if hbond < hbond_persistence_min:
                review_flags.append("weak_hbond_persistence")
            if contact < contact_persistence_min:
                review_flags.append("weak_contact_persistence")
            if not review_flags:
                band = BAND_GREEN
            else:
                band = BAND_YELLOW
                reason_code = review_flags[0]

    thresholds = {
        "local_min_survival_rmsd_a": local_min_survival_rmsd_a,
        "hbond_persistence_min": hbond_persistence_min,
        "contact_persistence_min": contact_persistence_min,
        "max_clash_count": max_clash_count,
    }
    uncertainty_score, uncertainty_posture = _uncertainty_posture(
        band=band,
        evidence_completeness=evidence_completeness,
        ligand_rmsd=ligand_rmsd,
        hbond=hbond,
        contact=contact,
        clash_count=clash_count,
        thresholds=thresholds,
        review_flags=review_flags,
    )

    return {
        "entry_id": entry_id,
        "family": family,
        "selected_for_refine": selected,
        "band": band,
        "claim_safe": band == BAND_GREEN,
        "abstained": band == BAND_ABSTAIN,
        "local_min_ligand_rmsd_a": ligand_rmsd,
        "local_min_survived": local_min_survived,
        "hbond_persistence": hbond,
        "contact_persistence": contact,
        "initial_clash_count": initial_clash_count,
        "clash_count": clash_count,
        "clash_relief_count": clash_relief_count,
        "clash_relief_observed": clash_relief_observed,
        "missing_evidence_fields": missing_evidence_fields,
        "evidence_completeness": evidence_completeness,
        "uncertainty_score": uncertainty_score,
        "uncertainty_posture": uncertainty_posture,
        "reason_code": reason_code,
        "review_flags": review_flags,
        "thresholds": thresholds,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_pocketmd_lite_report(
    candidates: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Grade a candidate set and roll up cascade KPIs."""

    rows = [build_pocketmd_lite_assessment(c, **kwargs) for c in candidates]
    band_counts = {
        BAND_GREEN: 0,
        BAND_YELLOW: 0,
        BAND_RED: 0,
        BAND_ABSTAIN: 0,
        BAND_COARSE_ONLY: 0,
    }
    for row in rows:
        band_counts[row["band"]] += 1

    refined = band_counts[BAND_GREEN] + band_counts[BAND_YELLOW] + band_counts[BAND_RED] + band_counts[BAND_ABSTAIN]
    green = band_counts[BAND_GREEN]
    abstain = band_counts[BAND_ABSTAIN]
    refined_rows = [row for row in rows if row["band"] != BAND_COARSE_ONLY]
    uncertainty_values = [
        float(row["uncertainty_score"])
        for row in refined_rows
        if row.get("uncertainty_score") is not None
    ]
    clash_relief_reported = [row for row in refined_rows if row.get("clash_relief_count") is not None]
    missing_metric_counts: dict[str, int] = {}
    for row in refined_rows:
        for metric in row.get("missing_evidence_fields", []):
            missing_metric_counts[metric] = missing_metric_counts.get(metric, 0) + 1
    local_min_reported_count = sum(1 for row in refined_rows if row.get("local_min_ligand_rmsd_a") is not None)
    hbond_reported_count = sum(1 for row in refined_rows if row.get("hbond_persistence") is not None)
    contact_reported_count = sum(1 for row in refined_rows if row.get("contact_persistence") is not None)
    initial_clash_reported_count = sum(1 for row in refined_rows if row.get("initial_clash_count") is not None)
    final_clash_reported_count = sum(1 for row in refined_rows if row.get("clash_count") is not None)

    summary = {
        "schema_version": POCKETMD_LITE_SCHEMA_VERSION,
        "candidate_count": len(rows),
        "refined_count": refined,
        "coarse_only_count": band_counts[BAND_COARSE_ONLY],
        "band_counts": band_counts,
        # KPIs: fraction of refined candidates that are claim-safe, and abstention rate.
        "refine_claim_safe_rate": (round(green / refined, 6) if refined else 0.0),
        "abstention_rate": (round(abstain / refined, 6) if refined else 0.0),
        "mean_uncertainty_score": round(sum(uncertainty_values) / len(uncertainty_values), 6)
        if uncertainty_values
        else None,
        "high_uncertainty_count": sum(1 for value in uncertainty_values if value >= 0.75),
        "local_min_survival_reported_count": local_min_reported_count,
        "local_min_survived_count": sum(1 for row in refined_rows if row.get("local_min_survived") is True),
        "hbond_persistence_reported_count": hbond_reported_count,
        "contact_persistence_reported_count": contact_reported_count,
        "initial_clash_reported_count": initial_clash_reported_count,
        "final_clash_reported_count": final_clash_reported_count,
        "clash_relief_reported_count": len(clash_relief_reported),
        "clash_relief_observed_count": sum(1 for row in clash_relief_reported if row["clash_relief_observed"] is True),
        "missing_refinement_evidence_count": abstain,
        "missing_refinement_metric_names": sorted(missing_metric_counts),
        "missing_refinement_metric_counts": dict(sorted(missing_metric_counts.items())),
        "top_k_refinement_evidence_ready": refined > 0 and abstain == 0,
        "reported_refinement_surface_counts": {
            "local_min_survival": local_min_reported_count,
            "contact_persistence": contact_reported_count,
            "hbond_persistence": hbond_reported_count,
            "clash_relief": len(clash_relief_reported),
            "uncertainty": len(uncertainty_values),
        },
        "metric_surfaces_reported": [
            "local_min_survival",
            "contact_persistence",
            "hbond_persistence",
            "clash_relief",
            "uncertainty",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


__all__ = [
    "POCKETMD_LITE_SCHEMA_VERSION",
    "TOPK_DEFAULT_THRESHOLD_PCT",
    "LOCAL_MIN_SURVIVAL_RMSD_A",
    "HBOND_PERSISTENCE_MIN",
    "CONTACT_PERSISTENCE_MIN",
    "MAX_CLASH_COUNT",
    "BAND_GREEN",
    "BAND_YELLOW",
    "BAND_RED",
    "BAND_ABSTAIN",
    "BAND_COARSE_ONLY",
    "CLAIM_BOUNDARY",
    "PocketMdLiteError",
    "is_refine_selected",
    "build_pocketmd_lite_assessment",
    "build_pocketmd_lite_report",
]
