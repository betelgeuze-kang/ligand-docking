from __future__ import annotations

from betelgeuze_product.hbond_backmap_report import (
    TIER_CLAIM_SAFE,
    TIER_EVIDENCE_ONLY,
    build_hbond_backmap_batch_report,
    build_hbond_backmap_report,
)


def _claim_safe_evidence() -> dict:
    return {
        "site_count": 3,
        "mapped_site_count": 3,
        "elements": ["O", "N", "N"],
        "roles": ["acceptor", "donor", "donor"],
        "role_counts": {"donor": 2, "acceptor": 1, "none": 0},
        "backmap_status": "ok",
        "mapping_source": "rdkit_etkdg",
        "input_bead_count": 2,
        "claim_safe": True,
        "blocked_reason": "",
        "abstention_reason": "",
        "max_onsps_sites": 4,
    }


def _fallback_evidence() -> dict:
    return {
        "site_count": 2,
        "mapped_site_count": 2,
        "elements": ["O", "N"],
        "roles": ["acceptor", "donor"],
        "role_counts": {"donor": 1, "acceptor": 1, "none": 0},
        "backmap_status": "ok",
        "mapping_source": "fallback_smiles",
        "input_bead_count": 2,
        "claim_safe": False,
        "blocked_reason": "onsps_fallback_not_claim_safe",
        "abstention_reason": "onsps_fallback_not_claim_safe",
        "max_onsps_sites": 4,
    }


def _no_sites_evidence() -> dict:
    return {
        "site_count": 0,
        "mapped_site_count": 0,
        "elements": [],
        "roles": [],
        "role_counts": {"donor": 0, "acceptor": 0, "none": 0},
        "backmap_status": "no_onsps_sites",
        "mapping_source": "rdkit_etkdg",
        "input_bead_count": 2,
        "claim_safe": False,
        "blocked_reason": "no_onsps_sites",
        "max_onsps_sites": 4,
    }


def test_claim_safe_report() -> None:
    report = build_hbond_backmap_report(
        _claim_safe_evidence(),
        entry_id="LIG-1",
        two_bead_vs_four_bead_delta=0.42,
        hbond_angle_score=0.91,
    )
    assert report["evidence_tier"] == TIER_CLAIM_SAFE
    assert report["claim_safe"] is True
    assert report["mapped_site_count"] == 3
    assert report["donor_count"] == 2
    assert report["acceptor_count"] == 1
    assert report["polar_site_elements"] == ["O", "N", "N"]
    assert report["mapping_source"] == "rdkit_etkdg"
    assert report["reason_code"] == ""
    assert report["two_bead_vs_four_bead_delta"] == 0.42
    assert report["hbond_angle_score"] == 0.91
    assert "not a docking" in report["claim_boundary"]


def test_fallback_is_evidence_only_with_structured_reason() -> None:
    report = build_hbond_backmap_report(_fallback_evidence(), entry_id="LIG-2")
    assert report["evidence_tier"] == TIER_EVIDENCE_ONLY
    assert report["claim_safe"] is False
    assert report["reason_code"] == "onsps_fallback_not_claim_safe"
    assert report["reason_detail"] == ""


def test_no_sites_is_evidence_only() -> None:
    report = build_hbond_backmap_report(_no_sites_evidence())
    assert report["claim_safe"] is False
    assert report["mapped_site_count"] == 0
    assert report["reason_code"] == "no_onsps_sites"


def test_empty_evidence_is_safe_default() -> None:
    report = build_hbond_backmap_report({})
    assert report["claim_safe"] is False
    assert report["evidence_tier"] == TIER_EVIDENCE_ONLY
    assert report["mapped_site_count"] == 0
    assert report["backmap_status"] == "not_assessed"


def test_role_counts_fallback_from_roles_list() -> None:
    evidence = _claim_safe_evidence()
    del evidence["role_counts"]
    report = build_hbond_backmap_report(evidence)
    assert report["donor_count"] == 2
    assert report["acceptor_count"] == 1


def test_optional_metrics_default_to_none() -> None:
    report = build_hbond_backmap_report(_claim_safe_evidence())
    assert report["two_bead_vs_four_bead_delta"] is None
    assert report["hbond_angle_score"] is None


def test_batch_report_claim_safe_rate_and_totals() -> None:
    rows = [
        {"entry_id": "a", "evidence": _claim_safe_evidence()},
        {"entry_id": "b", "evidence": _fallback_evidence()},
        {"entry_id": "c", "evidence": _no_sites_evidence()},
        {"entry_id": "d", "evidence": _claim_safe_evidence(), "hbond_angle_score": 0.8},
    ]
    batch = build_hbond_backmap_batch_report(rows)
    s = batch["summary"]
    assert s["candidate_count"] == 4
    assert s["claim_safe_count"] == 2
    assert s["evidence_only_count"] == 2
    assert s["claim_safe_rate"] == 0.5
    assert s["total_donor_sites"] == 2 + 1 + 0 + 2
    assert s["total_acceptor_sites"] == 1 + 1 + 0 + 1
    assert s["evidence_only_reason_counts"]["onsps_fallback_not_claim_safe"] == 1
    assert s["evidence_only_reason_counts"]["no_onsps_sites"] == 1
    assert len(batch["rows"]) == 4


def test_batch_report_empty() -> None:
    batch = build_hbond_backmap_batch_report([])
    assert batch["summary"]["candidate_count"] == 0
    assert batch["summary"]["claim_safe_rate"] == 0.0
