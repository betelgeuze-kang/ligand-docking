from __future__ import annotations

import pytest

from betelgeuze_product.gpcr_hard_decoy_suite import (
    DECOY_CLASS_OVER_ANCHORED,
    DECOY_CLASS_SAME_SIGNATURE,
    GpcrHardDecoyError,
    build_gpcr_hard_decoy_suite,
    build_target_hard_decoy_assessment,
)


def _green_target(target_id="HTR2A"):
    return {
        "target_id": target_id,
        "positive_count": 3,
        "ranking_pr_auc": 0.72,
        "ranking_pr_auc_ci_low": 0.55,
        "top20_hit_rate": 0.30,
        "decoys_above_positive_count": 0,
        "positive_target_rank": 1,
        "positive_anchor_distance_a": 3.10,
        "top_decoy_anchor_distance_a": 3.40,
        "decoy_class_counts": {},
    }


def _drd2_over_anchored():
    # Mirrors the real DRD2 diagnostic: decoy closer to anchor than positive.
    return {
        "target_id": "DRD2",
        "positive_count": 1,
        "ranking_pr_auc": 0.30,
        "ranking_pr_auc_ci_low": 0.02,
        "top20_hit_rate": 0.10,
        "decoys_above_positive_count": 5314,
        "positive_target_rank": 5315,
        "positive_anchor_distance_a": 3.25,
        "top_decoy_anchor_distance_a": 2.48,
        "decoy_class_counts": {DECOY_CLASS_OVER_ANCHORED: 10},
    }


def _oprm1_same_signature():
    return {
        "target_id": "OPRM1",
        "positive_count": 1,
        "ranking_pr_auc": 0.40,
        "ranking_pr_auc_ci_low": 0.12,
        "top20_hit_rate": 0.15,
        "decoys_above_positive_count": 157,
        "positive_target_rank": 158,
        "decoy_class_counts": {DECOY_CLASS_SAME_SIGNATURE: 157},
    }


def test_green_target_clears_gate() -> None:
    a = build_target_hard_decoy_assessment(_green_target())
    assert a["gate_status"] == "green"
    assert a["claim_safe"] is True
    assert a["blockers"] == []


def test_drd2_over_anchoring_blocks_with_root_cause() -> None:
    a = build_target_hard_decoy_assessment(_drd2_over_anchored())
    assert a["claim_safe"] is False
    assert "ranking_pr_auc_ci_low_below_gate" in a["blockers"]
    assert "top20_hit_rate_below_gate" in a["blockers"]
    assert "decoys_above_positive_present" in a["blockers"]
    assert "decoy_over_anchored_vs_positive" in a["blockers"]
    assert "anchor_separation_insufficient" in a["root_cause_tags"]
    assert "donor_prior_decoy_intrusion" in a["root_cause_tags"]


def test_oprm1_same_signature_root_cause() -> None:
    a = build_target_hard_decoy_assessment(_oprm1_same_signature())
    assert a["claim_safe"] is False
    assert "same_signature_no_discriminator" in a["root_cause_tags"]
    assert "decoys_above_positive_present" in a["blockers"]


def test_ci_low_exactly_at_gate_passes() -> None:
    row = _green_target()
    row["ranking_pr_auc_ci_low"] = 0.45
    row["top20_hit_rate"] = 0.20
    a = build_target_hard_decoy_assessment(row)
    assert a["claim_safe"] is True


def test_just_below_gate_blocks() -> None:
    row = _green_target()
    row["ranking_pr_auc_ci_low"] = 0.4499
    a = build_target_hard_decoy_assessment(row)
    assert a["claim_safe"] is False
    assert "ranking_pr_auc_ci_low_below_gate" in a["blockers"]


def test_missing_metrics_block() -> None:
    a = build_target_hard_decoy_assessment({"target_id": "DRD3", "positive_count": 1})
    assert a["claim_safe"] is False
    assert "ranking_pr_auc_ci_low_below_gate" in a["blockers"]
    assert "top20_hit_rate_below_gate" in a["blockers"]


def test_missing_required_field_raises() -> None:
    with pytest.raises(GpcrHardDecoyError):
        build_target_hard_decoy_assessment({"target_id": "x"})


def test_unknown_decoy_class_raises() -> None:
    row = _green_target()
    row["decoy_class_counts"] = {"teleport_decoy": 3}
    with pytest.raises(GpcrHardDecoyError):
        build_target_hard_decoy_assessment(row)


# --- family rollup ---


def test_family_locked_when_any_required_blocked() -> None:
    suite = build_gpcr_hard_decoy_suite(
        [_green_target("HTR2A"), _drd2_over_anchored(), _oprm1_same_signature()]
    )
    s = suite["summary"]
    assert s["family_claim_safe"] is False
    assert s["status"] == "broad_family_locked"
    assert "DRD2" in s["blocked_target_ids"]
    assert "HTR2A" in s["green_target_ids"]
    assert s["first_blocked_required_target"] == "DRD2"


def test_family_ready_when_all_required_green() -> None:
    suite = build_gpcr_hard_decoy_suite(
        [_green_target("DRD2"), _green_target("HTR2A"), _green_target("OPRM1")]
    )
    s = suite["summary"]
    assert s["family_claim_safe"] is True
    assert s["status"] == "gpcr_hard_decoy_family_ready"
    assert set(s["green_target_ids"]) == {"DRD2", "HTR2A", "OPRM1"}


def test_missing_required_target_locks_family() -> None:
    suite = build_gpcr_hard_decoy_suite([_green_target("DRD2"), _green_target("HTR2A")])
    s = suite["summary"]
    assert s["family_claim_safe"] is False
    assert "OPRM1" in s["missing_required_target_ids"]


def test_custom_required_set() -> None:
    suite = build_gpcr_hard_decoy_suite(
        [_green_target("DRD2")], required_target_ids=["DRD2"]
    )
    assert suite["summary"]["family_claim_safe"] is True
