from __future__ import annotations

import pytest

from betelgeuze_product.pocketmd_lite_contract import (
    BAND_ABSTAIN,
    BAND_COARSE_ONLY,
    BAND_GREEN,
    BAND_RED,
    BAND_YELLOW,
    PocketMdLiteError,
    build_pocketmd_lite_assessment,
    build_pocketmd_lite_report,
    is_refine_selected,
)


def _green_candidate(entry_id="LIG-1"):
    return {
        "entry_id": entry_id,
        "family": "gpcr",
        "rank_pct": 0.01,
        "local_min_ligand_rmsd_a": 1.5,
        "hbond_persistence": 0.8,
        "contact_persistence": 0.75,
        "clash_count": 0,
    }


def test_selection_family_lane() -> None:
    assert is_refine_selected(family="gpcr") is True
    assert is_refine_selected(family="kinase") is True
    assert is_refine_selected(family="transporter") is False


def test_selection_by_rank_pct() -> None:
    assert is_refine_selected(family="transporter", rank_pct=0.02) is True
    assert is_refine_selected(family="transporter", rank_pct=0.20) is False
    assert is_refine_selected(family="transporter", rank_pct=None) is False


def test_green_band_is_claim_safe() -> None:
    a = build_pocketmd_lite_assessment(_green_candidate())
    assert a["band"] == BAND_GREEN
    assert a["claim_safe"] is True
    assert a["local_min_survived"] is True
    assert a["review_flags"] == []
    assert a["reason_code"] == ""


def test_failed_survival_is_red() -> None:
    c = _green_candidate()
    c["local_min_ligand_rmsd_a"] = 3.5  # > 2.0 threshold
    a = build_pocketmd_lite_assessment(c)
    assert a["band"] == BAND_RED
    assert a["claim_safe"] is False
    assert a["local_min_survived"] is False
    assert a["reason_code"] == "local_min_did_not_survive"


def test_weak_persistence_is_yellow() -> None:
    c = _green_candidate()
    c["hbond_persistence"] = 0.3  # < 0.5
    a = build_pocketmd_lite_assessment(c)
    assert a["band"] == BAND_YELLOW
    assert a["claim_safe"] is False
    assert "weak_hbond_persistence" in a["review_flags"]


def test_residual_clash_is_yellow() -> None:
    c = _green_candidate()
    c["clash_count"] = 2
    a = build_pocketmd_lite_assessment(c)
    assert a["band"] == BAND_YELLOW
    assert "residual_clash" in a["review_flags"]


def test_missing_evidence_abstains() -> None:
    c = _green_candidate()
    c["hbond_persistence"] = None
    a = build_pocketmd_lite_assessment(c)
    assert a["band"] == BAND_ABSTAIN
    assert a["abstained"] is True
    assert a["reason_code"] == "missing_refinement_evidence"


def test_not_selected_is_coarse_only() -> None:
    c = {"entry_id": "LIG-9", "family": "transporter", "rank_pct": 0.5}
    a = build_pocketmd_lite_assessment(c)
    assert a["band"] == BAND_COARSE_ONLY
    assert a["selected_for_refine"] is False
    assert a["claim_safe"] is False


def test_explicit_selected_flag_overrides() -> None:
    c = _green_candidate()
    c["family"] = "transporter"
    c["rank_pct"] = 0.5
    c["selected_for_refine"] = True
    a = build_pocketmd_lite_assessment(c)
    assert a["selected_for_refine"] is True
    assert a["band"] == BAND_GREEN


def test_survival_threshold_boundary() -> None:
    c = _green_candidate()
    c["local_min_ligand_rmsd_a"] = 2.0  # exactly at threshold passes
    assert build_pocketmd_lite_assessment(c)["local_min_survived"] is True


def test_missing_entry_id_raises() -> None:
    with pytest.raises(PocketMdLiteError):
        build_pocketmd_lite_assessment({"family": "gpcr"})


def test_non_numeric_metric_raises() -> None:
    c = _green_candidate()
    c["hbond_persistence"] = "high"
    with pytest.raises(PocketMdLiteError):
        build_pocketmd_lite_assessment(c)


def test_batch_report_kpis() -> None:
    candidates = [
        _green_candidate("a"),
        {**_green_candidate("b"), "hbond_persistence": 0.2},  # yellow
        {**_green_candidate("c"), "local_min_ligand_rmsd_a": 4.0},  # red
        {**_green_candidate("d"), "clash_count": None},  # abstain
        {"entry_id": "e", "family": "transporter", "rank_pct": 0.9},  # coarse_only
    ]
    report = build_pocketmd_lite_report(candidates)
    s = report["summary"]
    assert s["candidate_count"] == 5
    assert s["refined_count"] == 4
    assert s["coarse_only_count"] == 1
    assert s["band_counts"][BAND_GREEN] == 1
    assert s["band_counts"][BAND_YELLOW] == 1
    assert s["band_counts"][BAND_RED] == 1
    assert s["band_counts"][BAND_ABSTAIN] == 1
    assert s["refine_claim_safe_rate"] == 0.25
    assert s["abstention_rate"] == 0.25


def test_empty_report() -> None:
    s = build_pocketmd_lite_report([])["summary"]
    assert s["candidate_count"] == 0
    assert s["refine_claim_safe_rate"] == 0.0
    assert s["abstention_rate"] == 0.0
