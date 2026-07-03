from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api import product_hbond_backmap as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_hbond_backmap_report_returns_dashboard_safe_candidate_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "runs/hbond_backmap_report_current.json"
    monkeypatch.setattr(mod, "HBOND_BACKMAP_REPORT_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "status": "hbond_backmap_report_ready",
            "summary": {
                "report_version": "hbond_backmap_report_v1",
                "candidate_count": 2,
                "claim_safe_count": 1,
                "evidence_only_count": 1,
                "claim_safe_rate": 0.5,
                "total_donor_sites": 2,
                "total_acceptor_sites": 1,
                "evidence_only_reason_counts": {"no_onsps_sites": 1},
                "claim_boundary": "hbond fixture boundary",
            },
            "rows": [
                {
                    "entry_id": "LIG-1",
                    "evidence_tier": "claim_safe",
                    "claim_safe": True,
                    "mapped_site_count": "3",
                    "site_count": 3,
                    "max_onsps_sites": 4,
                    "donor_count": 2,
                    "acceptor_count": 1,
                    "polar_site_elements": ["O", "N", ""],
                    "mapping_source": "rdkit_etkdg",
                    "backmap_status": "ok",
                    "reason_code": "",
                    "reason_detail": "",
                    "two_bead_vs_four_bead_delta": "0.42",
                    "hbond_angle_score": 0.91,
                    "execution_enabled": True,
                    "docking_results_emitted": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "entry_id": "LIG-2",
                    "evidence_tier": "evidence_only",
                    "claim_safe": False,
                    "mapped_site_count": 0,
                    "site_count": 0,
                    "max_onsps_sites": 4,
                    "donor_count": 0,
                    "acceptor_count": 0,
                    "polar_site_elements": "O;N",
                    "mapping_source": "fallback_smiles",
                    "backmap_status": "no_onsps_sites",
                    "reason_code": "no_onsps_sites",
                    "reason_detail": "no polar sites",
                    "two_bead_vs_four_bead_delta": "",
                    "hbond_angle_score": None,
                    "claim_boundary": "row-specific boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
        },
    )

    response = asyncio.run(mod.get_product_hbond_backmap_report())

    assert response["status"] == "hbond_backmap_report_ready"
    assert response["candidate_table_ready"] is True
    assert response["candidate_row_count"] == 2
    assert response["claim_safe_candidate_row_count"] == 1
    assert response["evidence_only_candidate_row_count"] == 1
    assert len(response["candidates"]) == 2
    assert response["candidate_rows"] == [
        {
            "entry_id": "LIG-1",
            "evidence_tier": "claim_safe",
            "claim_safe": True,
            "evidence_only": False,
            "mapped_site_count": 3,
            "site_count": 3,
            "max_onsps_sites": 4,
            "donor_count": 2,
            "acceptor_count": 1,
            "polar_site_elements": ["O", "N"],
            "mapping_source": "rdkit_etkdg",
            "backmap_status": "ok",
            "reason_code": "",
            "reason_detail": "",
            "two_bead_vs_four_bead_delta": 0.42,
            "hbond_angle_score": 0.91,
            "operator_action_required": False,
            "claim_boundary": "hbond fixture boundary",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "entry_id": "LIG-2",
            "evidence_tier": "evidence_only",
            "claim_safe": False,
            "evidence_only": True,
            "mapped_site_count": 0,
            "site_count": 0,
            "max_onsps_sites": 4,
            "donor_count": 0,
            "acceptor_count": 0,
            "polar_site_elements": ["O", "N"],
            "mapping_source": "fallback_smiles",
            "backmap_status": "no_onsps_sites",
            "reason_code": "no_onsps_sites",
            "reason_detail": "no polar sites",
            "two_bead_vs_four_bead_delta": None,
            "hbond_angle_score": None,
            "operator_action_required": True,
            "claim_boundary": "row-specific boundary",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False


def test_hbond_backmap_missing_artifact_keeps_dashboard_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "HBOND_BACKMAP_REPORT_ARTIFACT",
        tmp_path / "runs/missing_hbond_backmap_report_current.json",
    )

    response = asyncio.run(mod.get_product_hbond_backmap_report())

    assert response["status"] == "missing_hbond_backmap_report"
    assert response["candidate_table_ready"] is False
    assert response["candidate_row_count"] == 0
    assert response["claim_safe_candidate_row_count"] == 0
    assert response["evidence_only_candidate_row_count"] == 0
    assert response["candidate_rows"] == []
    assert response["candidates"] == []
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False
