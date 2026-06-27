"""Customer/GUI report surface for H-Bond BackMap (ONSPS-4).

H-Bond BackMap is a product differentiator: it reconstructs up to four
O/N/P/S donor/acceptor sites from a fast coarse 2-bead representation so that
H-bond-aware rescoring and *interpretable* evidence can be shown, while keeping
the cheap screening path. The science lives in
``betelgeuze_engine.backmapping.onsps`` (numpy/RDKit); this module is the
dependency-free **report/governance layer** that turns the engine's evidence
dict into a stable, claim-safe report for the GUI, the candidate table, and
evidence bundles.

Governance (same posture as the benchmark ledger):

- H-Bond BackMap is **local interpretability evidence**, not a docking-accuracy
  or binding-affinity claim. The report never says "more accurate".
- A row is ``claim_safe`` only when the engine produced an RDKit-ETKDG mapping
  with valid 2-bead geometry and at least one mapped site. Fallback/empty/no-site
  rows are surfaced as ``evidence_only`` with a structured reason, never as a
  positive H-bond claim.

Dependency-free (stdlib + ``betelgeuze_product.structured_reason``) so it is
unit-testable without numpy/RDKit/FastAPI.
"""

from __future__ import annotations

from typing import Any

from betelgeuze_product.structured_reason import reason_fields

HBOND_BACKMAP_REPORT_VERSION = "hbond_backmap_report_v1"
MAX_ONSPS_SITES = 4

CLAIM_BOUNDARY = (
    "H-Bond BackMap reconstructs up to four O/N/P/S donor/acceptor sites from a coarse 2-bead representation "
    "for interpretable, H-bond-aware rescoring evidence. It is local interpretability evidence, not a docking "
    "accuracy or binding-affinity claim, and not a substitute for all-atom MD. claim_safe=true requires an "
    "RDKit-ETKDG mapping with valid 2-bead geometry and at least one mapped polar site."
)

TIER_CLAIM_SAFE = "claim_safe"
TIER_EVIDENCE_ONLY = "evidence_only"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _role_counts(evidence: dict[str, Any]) -> dict[str, int]:
    counts = evidence.get("role_counts")
    if isinstance(counts, dict):
        return {
            "donor": _int(counts.get("donor")),
            "acceptor": _int(counts.get("acceptor")),
            "none": _int(counts.get("none")),
        }
    # Fall back to counting the roles list.
    roles = evidence.get("roles") or []
    roles = [str(r) for r in roles] if isinstance(roles, (list, tuple)) else []
    return {
        "donor": sum(1 for r in roles if r == "donor"),
        "acceptor": sum(1 for r in roles if r == "acceptor"),
        "none": sum(1 for r in roles if r == "none"),
    }


def build_hbond_backmap_report(
    evidence: dict[str, Any],
    *,
    entry_id: str = "",
    two_bead_vs_four_bead_delta: float | None = None,
    hbond_angle_score: float | None = None,
) -> dict[str, Any]:
    """Build a stable, claim-safe H-Bond BackMap report from engine evidence.

    ``evidence`` is the meta dict returned by
    ``betelgeuze_engine.backmapping.onsps.backmap_4bead_onsps`` (or
    ``OnspsBackmapEvidence.to_dict()``). ``two_bead_vs_four_bead_delta`` and
    ``hbond_angle_score`` are optional scoring-path values surfaced for review.
    """

    if not isinstance(evidence, dict):
        evidence = {}
    claim_safe = evidence.get("claim_safe") is True
    role_counts = _role_counts(evidence)
    # The engine encodes the gate reason in blocked_reason/abstention_reason.
    reason_text = str(evidence.get("blocked_reason") or evidence.get("abstention_reason") or "")
    if claim_safe:
        reason_text = ""
    structured = reason_fields(reason_text)

    elements = evidence.get("elements") or []
    elements = [str(e) for e in elements] if isinstance(elements, (list, tuple)) else []

    report: dict[str, Any] = {
        "report_version": HBOND_BACKMAP_REPORT_VERSION,
        "entry_id": str(entry_id),
        "evidence_tier": TIER_CLAIM_SAFE if claim_safe else TIER_EVIDENCE_ONLY,
        "claim_safe": bool(claim_safe),
        "mapped_site_count": _int(evidence.get("mapped_site_count")),
        "site_count": _int(evidence.get("site_count")),
        "max_onsps_sites": _int(evidence.get("max_onsps_sites"), MAX_ONSPS_SITES),
        "donor_count": role_counts["donor"],
        "acceptor_count": role_counts["acceptor"],
        "polar_site_elements": elements,
        "mapping_source": str(evidence.get("mapping_source") or ""),
        "backmap_status": str(evidence.get("backmap_status") or "not_assessed"),
        "reason_code": structured["reason_code"],
        "reason_detail": structured["reason_detail"],
        "two_bead_vs_four_bead_delta": (
            None if two_bead_vs_four_bead_delta is None else float(two_bead_vs_four_bead_delta)
        ),
        "hbond_angle_score": (None if hbond_angle_score is None else float(hbond_angle_score)),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return report


def build_hbond_backmap_batch_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-candidate H-Bond BackMap reports into a batch summary.

    ``rows`` is a list of ``{"entry_id", "evidence", optional delta/angle}``
    dicts. Returns ``{"summary", "rows"}`` where summary carries the claim-safe
    rate KPI and donor/acceptor totals.
    """

    reports: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        reports.append(
            build_hbond_backmap_report(
                row.get("evidence") or {},
                entry_id=str(row.get("entry_id", "")),
                two_bead_vs_four_bead_delta=row.get("two_bead_vs_four_bead_delta"),
                hbond_angle_score=row.get("hbond_angle_score"),
            )
        )

    total = len(reports)
    claim_safe_count = sum(1 for r in reports if r["claim_safe"])
    evidence_only_count = total - claim_safe_count
    reason_counts: dict[str, int] = {}
    for r in reports:
        if not r["claim_safe"] and r["reason_code"]:
            reason_counts[r["reason_code"]] = reason_counts.get(r["reason_code"], 0) + 1

    summary = {
        "report_version": HBOND_BACKMAP_REPORT_VERSION,
        "candidate_count": total,
        "claim_safe_count": claim_safe_count,
        "evidence_only_count": evidence_only_count,
        # KPI: fraction of candidates with a claim-safe H-bond reconstruction.
        "claim_safe_rate": (round(claim_safe_count / total, 6) if total else 0.0),
        "total_donor_sites": sum(r["donor_count"] for r in reports),
        "total_acceptor_sites": sum(r["acceptor_count"] for r in reports),
        "evidence_only_reason_counts": reason_counts,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": reports}


__all__ = [
    "HBOND_BACKMAP_REPORT_VERSION",
    "MAX_ONSPS_SITES",
    "CLAIM_BOUNDARY",
    "TIER_CLAIM_SAFE",
    "TIER_EVIDENCE_ONLY",
    "build_hbond_backmap_report",
    "build_hbond_backmap_batch_report",
]
