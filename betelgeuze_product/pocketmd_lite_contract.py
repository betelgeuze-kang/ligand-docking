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

# Top-k selection: only the cheapest-to-trust fraction (or family lanes) get the
# expensive refinement, keeping the cascade affordable.
TOPK_DEFAULT_THRESHOLD_PCT = 0.05
_REFINE_FAMILIES = frozenset({"gpcr", "kinase", "ion_channel"})

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
    "threshold, and no residual clash. Missing evidence abstains; failed survival is red. It is not all-atom MD, "
    "not a binding-affinity claim, and refines only selected top-k candidates. The refinement computation runs "
    "elsewhere; this layer selects, grades, and governs."
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

    fam = str(family or "").strip().lower().replace("-", "_")
    if fam in _REFINE_FAMILIES:
        return True
    if rank_pct is None:
        return False
    return float(rank_pct) <= float(top_k_threshold_pct)


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
    clash = candidate.get("clash_count")
    clash_count = None if clash in (None, "") else int(clash)

    reason_code = ""
    review_flags: list[str] = []

    if not selected:
        band = BAND_COARSE_ONLY
        reason_code = "not_selected_for_refine"
        local_min_survived = None
    elif ligand_rmsd is None or hbond is None or contact is None or clash_count is None:
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
        "clash_count": clash_count,
        "reason_code": reason_code,
        "review_flags": review_flags,
        "thresholds": {
            "local_min_survival_rmsd_a": local_min_survival_rmsd_a,
            "hbond_persistence_min": hbond_persistence_min,
            "contact_persistence_min": contact_persistence_min,
            "max_clash_count": max_clash_count,
        },
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

    summary = {
        "schema_version": POCKETMD_LITE_SCHEMA_VERSION,
        "candidate_count": len(rows),
        "refined_count": refined,
        "coarse_only_count": band_counts[BAND_COARSE_ONLY],
        "band_counts": band_counts,
        # KPIs: fraction of refined candidates that are claim-safe, and abstention rate.
        "refine_claim_safe_rate": (round(green / refined, 6) if refined else 0.0),
        "abstention_rate": (round(abstain / refined, 6) if refined else 0.0),
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
