"""GPCR hard-decoy suite contract (DRD2 / HTR2A / OPRM1), read-only.

Broad GPCR-family / router claim is the repo's main remaining ranking blocker.
The diagnostics for it are real but scattered across many `runs/` artifacts
(over-anchored DRD2 decoys, OPRM1 same-signature decoys, HTR2A decoy support).
This module turns that into ONE official, measurable hard-decoy benchmark
contract: a fixed decoy taxonomy, target-internal separation metrics, and a
fail-closed claim gate. It computes no scoring; it evaluates caller-provided
per-target aggregate rows (the same numbers already produced by the GPCR
diagnostics packets) and decides claim status.

Dependency-free so it is unit-testable without numpy.
"""

from __future__ import annotations

from typing import Any

GPCR_HARD_DECOY_SCHEMA_VERSION = "gpcr_hard_decoy_suite_v1"

# Operational claim gate (matches the repo's existing GPCR claim-review rule).
GATE_CI_LOW = 0.45
GATE_TOP20 = 0.20

# Hard-decoy taxonomy (why a decoy is hard to separate from the positive).
DECOY_CLASS_OVER_ANCHORED = "over_anchored"  # decoy sits closer to the native anchor than the positive
DECOY_CLASS_SAME_SIGNATURE = "same_signature"  # decoy shares the positive's feature signature
DECOY_CLASS_MULTIPOLAR = "multipolar"  # multipolar/basic decoy promoted by polar reward
DECOY_CLASS_POSE_DISTORTED_VALID_ANCHOR = "pose_distorted_valid_anchor"
DECOY_CLASS_VALID_ANCHOR_CHALLENGE = "valid_anchor_challenge"
DECOY_CLASS_GENERIC = "generic"

DECOY_CLASSES = frozenset(
    {
        DECOY_CLASS_OVER_ANCHORED,
        DECOY_CLASS_SAME_SIGNATURE,
        DECOY_CLASS_MULTIPOLAR,
        DECOY_CLASS_POSE_DISTORTED_VALID_ANCHOR,
        DECOY_CLASS_VALID_ANCHOR_CHALLENGE,
        DECOY_CLASS_GENERIC,
    }
)

# Root-cause tags (kept aligned with the GPCR regression-triage vocabulary).
ROOT_CAUSE_DONOR_PRIOR_DECOY_INTRUSION = "donor_prior_decoy_intrusion"
ROOT_CAUSE_WEAK_CONTACT_PRIOR_MISMATCH = "weak_contact_prior_mismatch"
ROOT_CAUSE_AFFINITY_HINT_MD_SUPPORT_MISMATCH = "affinity_hint_md_support_mismatch"
ROOT_CAUSE_SAME_SIGNATURE_NO_DISCRIMINATOR = "same_signature_no_discriminator"
ROOT_CAUSE_ANCHOR_SEPARATION_INSUFFICIENT = "anchor_separation_insufficient"

CLAIM_BOUNDARY = (
    "GPCR hard-decoy suite contract. It evaluates caller-provided per-target ranking/decoy-separation rows "
    "against the fixed operational gate (ranking_pr_auc_ci_low >= 0.45 AND top20_hit_rate >= 0.20) plus "
    "target-internal decoy separation. A target stays blocked until it clears the gate, and the broad GPCR/router "
    "family claim stays locked until every required target clears. It does not run scoring, generate decoys, relax "
    "thresholds, or emit a positive broad-family claim."
)

_REQUIRED_TARGET_FIELDS = ("target_id", "positive_count")


class GpcrHardDecoyError(ValueError):
    """Raised when a target row is malformed."""


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise GpcrHardDecoyError(f"non-numeric value: {value!r}") from exc


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _decoy_class_counts(raw: Any) -> dict[str, int]:
    counts = {cls: 0 for cls in sorted(DECOY_CLASSES)}
    if isinstance(raw, dict):
        for key, value in raw.items():
            cls = str(key)
            if cls not in DECOY_CLASSES:
                raise GpcrHardDecoyError(f"unknown decoy_class: {cls}")
            counts[cls] = _int(value)
    return counts


def build_target_hard_decoy_assessment(row: dict[str, Any]) -> dict[str, Any]:
    """Assess one GPCR target against the hard-decoy claim gate (fail-closed)."""

    for field in _REQUIRED_TARGET_FIELDS:
        if field not in row:
            raise GpcrHardDecoyError(f"target row missing required field: {field}")

    target_id = str(row["target_id"])
    positive_count = _int(row["positive_count"])
    ci_low = _num(row.get("ranking_pr_auc_ci_low"))
    top20 = _num(row.get("top20_hit_rate"))
    pr_auc = _num(row.get("ranking_pr_auc"))
    decoys_above_raw = row.get("decoys_above_positive_count")
    decoys_above_missing = decoys_above_raw in (None, "")
    decoys_above = _int(decoys_above_raw)
    target_rank = row.get("positive_target_rank")
    positive_anchor_a = _num(row.get("positive_anchor_distance_a"))
    top_decoy_anchor_a = _num(row.get("top_decoy_anchor_distance_a"))
    retained_target_row_count = _int(row.get("retained_target_row_count"))
    retained_positive_count = _int(row.get("retained_positive_count"))
    top_decoy_retained_count_raw = row.get("top_decoy_retained_count")
    top_decoy_retained_count = None if top_decoy_retained_count_raw in (None, "") else _int(top_decoy_retained_count_raw)
    anchor_margin_a = (
        None
        if positive_anchor_a is None or top_decoy_anchor_a is None
        else top_decoy_anchor_a - positive_anchor_a
    )
    decoy_class_counts = _decoy_class_counts(row.get("decoy_class_counts"))

    blockers: list[str] = []
    root_cause_tags: list[str] = []

    if positive_count <= 0:
        blockers.append("positive_count_missing_or_zero")

    # Operational gate.
    if ci_low is None or ci_low < GATE_CI_LOW:
        blockers.append("ranking_pr_auc_ci_low_below_gate")
    if top20 is None or top20 < GATE_TOP20:
        blockers.append("top20_hit_rate_below_gate")

    # Target-internal decoy separation.
    if decoys_above_missing:
        blockers.append("decoys_above_positive_count_missing")
    if decoys_above > 0:
        blockers.append("decoys_above_positive_present")
    if positive_anchor_a is None:
        blockers.append("anchor_distance_evidence_missing")
    if top_decoy_anchor_a is None:
        if top_decoy_retained_count == 0:
            blockers.append("top_decoy_anchor_not_observed_in_retained_rows")
        elif positive_anchor_a is not None:
            blockers.append("top_decoy_anchor_distance_evidence_missing")
        elif "anchor_distance_evidence_missing" not in blockers:
            blockers.append("anchor_distance_evidence_missing")
    # Over-anchoring: a decoy sits closer to the native anchor than the positive.
    if anchor_margin_a is not None and anchor_margin_a < 0.0:
        blockers.append("decoy_over_anchored_vs_positive")
        root_cause_tags.append(ROOT_CAUSE_ANCHOR_SEPARATION_INSUFFICIENT)

    # Root-cause tags from decoy classes.
    if decoy_class_counts[DECOY_CLASS_OVER_ANCHORED] > 0:
        root_cause_tags.append(ROOT_CAUSE_DONOR_PRIOR_DECOY_INTRUSION)
    if decoy_class_counts[DECOY_CLASS_SAME_SIGNATURE] > 0:
        root_cause_tags.append(ROOT_CAUSE_SAME_SIGNATURE_NO_DISCRIMINATOR)
    if decoy_class_counts[DECOY_CLASS_MULTIPOLAR] > 0:
        root_cause_tags.append(ROOT_CAUSE_WEAK_CONTACT_PRIOR_MISMATCH)

    gate_status = "green" if not blockers else "blocked"

    return {
        "target_id": target_id,
        "gate_status": gate_status,
        "claim_safe": gate_status == "green",
        "positive_count": positive_count,
        "ranking_pr_auc": pr_auc,
        "ranking_pr_auc_ci_low": ci_low,
        "top20_hit_rate": top20,
        "positive_target_rank": _int(target_rank) if target_rank not in (None, "") else None,
        "decoys_above_positive_count": None if decoys_above_missing else decoys_above,
        "positive_anchor_distance_a": positive_anchor_a,
        "top_decoy_anchor_distance_a": top_decoy_anchor_a,
        "anchor_margin_a": anchor_margin_a,
        "retained_target_row_count": retained_target_row_count,
        "retained_positive_count": retained_positive_count,
        "top_decoy_retained_count": top_decoy_retained_count,
        "decoy_class_counts": decoy_class_counts,
        "blockers": blockers,
        "root_cause_tags": sorted(set(root_cause_tags)),
        "gate": {"ci_low_min": GATE_CI_LOW, "top20_min": GATE_TOP20},
    }


def build_gpcr_hard_decoy_suite(
    targets: list[dict[str, Any]],
    *,
    required_target_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Roll up per-target assessments into a family claim decision (fail-closed).

    The broad GPCR/router family claim is allowed only when every required
    target clears the gate. Default required set: DRD2, HTR2A, OPRM1.
    """

    required = list(required_target_ids) if required_target_ids is not None else ["DRD2", "HTR2A", "OPRM1"]
    assessments = [build_target_hard_decoy_assessment(row) for row in targets]
    by_id = {a["target_id"]: a for a in assessments}

    green_targets = [a["target_id"] for a in assessments if a["claim_safe"]]
    blocked_targets = [a["target_id"] for a in assessments if not a["claim_safe"]]
    missing_required = [tid for tid in required if tid not in by_id]

    family_claim_safe = (not missing_required) and all(
        by_id.get(tid, {}).get("claim_safe") is True for tid in required
    )

    # First blocker for operator focus.
    first_blocked = next((tid for tid in required if not by_id.get(tid, {}).get("claim_safe", False)), "")

    summary = {
        "schema_version": GPCR_HARD_DECOY_SCHEMA_VERSION,
        "status": "gpcr_hard_decoy_family_ready" if family_claim_safe else "broad_family_locked",
        "family_claim_safe": family_claim_safe,
        "required_target_ids": required,
        "target_count": len(assessments),
        "green_target_ids": green_targets,
        "blocked_target_ids": blocked_targets,
        "missing_required_target_ids": missing_required,
        "first_blocked_required_target": first_blocked,
        "gate": {"ci_low_min": GATE_CI_LOW, "top20_min": GATE_TOP20},
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "targets": assessments}


__all__ = [
    "GPCR_HARD_DECOY_SCHEMA_VERSION",
    "GATE_CI_LOW",
    "GATE_TOP20",
    "DECOY_CLASSES",
    "DECOY_CLASS_OVER_ANCHORED",
    "DECOY_CLASS_SAME_SIGNATURE",
    "DECOY_CLASS_MULTIPOLAR",
    "DECOY_CLASS_POSE_DISTORTED_VALID_ANCHOR",
    "DECOY_CLASS_VALID_ANCHOR_CHALLENGE",
    "DECOY_CLASS_GENERIC",
    "CLAIM_BOUNDARY",
    "GpcrHardDecoyError",
    "build_target_hard_decoy_assessment",
    "build_gpcr_hard_decoy_suite",
]
