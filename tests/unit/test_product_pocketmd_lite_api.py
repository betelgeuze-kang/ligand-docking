from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def test_pocketmd_lite_topk_refinement_audit_endpoint_reads_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    artifact = tmp_path / "pocketmd_lite_topk_refinement_audit_current.json"
    artifact.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported",
                    "schema_version": "pocketmd_lite_topk_refinement_audit_v1",
                    "candidate_count": 5,
                    "selected_top_k_count": 5,
                    "claim_grade_refinement_evidence_ready": False,
                    "claim_grade_report_evidence_ready": False,
                    "proxy_topk_telemetry_ready": True,
                    "claim_grade_metric_ready_count": 0,
                    "claim_grade_missing_candidate_count": 5,
                    "claim_grade_band_counts": {
                        "green": 0,
                        "yellow": 0,
                        "red": 0,
                        "abstain": 5,
                    },
                    "green_row_count": 0,
                    "yellow_row_count": 0,
                    "red_row_count": 0,
                    "abstain_row_count": 5,
                    "claim_grade_fill_preview_evidence_ready": False,
                    "claim_grade_local_min_reported_count": 1,
                    "claim_grade_local_min_survival_count": 1,
                    "claim_grade_hbond_reported_count": 1,
                    "claim_grade_contact_reported_count": 1,
                    "claim_grade_initial_clash_reported_count": 1,
                    "claim_grade_final_clash_reported_count": 1,
                    "claim_grade_clash_relief_reported_count": 1,
                    "missing_refinement_metric_names": ["hbond_persistence"],
                    "missing_refinement_metric_counts": {"hbond_persistence": 5},
                    "green_band_condition_text": "green requires exact metrics",
                    "top_k_only_policy_enforced": True,
                    "claim_promotion_allowed": False,
                },
                "rows": [
                    {
                        "entry_id": "ADRB2.compound_001",
                        "local_min_ligand_rmsd_a": "1.2",
                        "hbond_persistence": "0.8",
                        "contact_persistence": "0.9",
                        "initial_clash_count": "10",
                        "clash_count": "1",
                        "clash_relief_count": "9",
                    }
                ],
                "claim_boundary": "Proxy telemetry cannot satisfy claim-grade refinement evidence.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT", artifact)

    payload = asyncio.run(mod.get_product_pocketmd_lite_topk_refinement_audit())

    assert payload["status"] == "blocked_pocketmd_lite_topk_refinement_claim_grade_missing_proxy_reported"
    assert payload["selected_top_k_count"] == 5
    assert payload["claim_grade_refinement_evidence_ready"] is False
    assert payload["proxy_topk_telemetry_ready"] is True
    assert payload["claim_grade_band_counts"]["abstain"] == 5
    assert payload["abstain_row_count"] == 5
    assert payload["claim_grade_local_min_reported_count"] == 1
    assert payload["claim_grade_clash_relief_reported_count"] == 1
    assert payload["local_min_ligand_rmsd_a_max"] == 1.2
    assert payload["hbond_persistence_min"] == 0.8
    assert payload["contact_persistence_min"] == 0.9
    assert payload["initial_clash_count_total"] == 10
    assert payload["final_clash_count_total"] == 1
    assert payload["clash_relief_count_total"] == 9
    assert payload["green_band_condition_text"] == "green requires exact metrics"
    assert payload["top_k_only_policy_enforced"] is True
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
    assert payload["rows"][0]["entry_id"] == "ADRB2.compound_001"


def test_pocketmd_lite_topk_refinement_audit_endpoint_is_fail_closed_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from api import product_pocketmd_lite as mod

    monkeypatch.setattr(mod, "POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_ARTIFACT", tmp_path / "missing.json")

    payload = asyncio.run(mod.get_product_pocketmd_lite_topk_refinement_audit())

    assert payload["status"] == "missing_pocketmd_lite_topk_refinement_audit"
    assert payload["claim_grade_refinement_evidence_ready"] is False
    assert payload["proxy_topk_telemetry_ready"] is False
    assert payload["claim_grade_band_counts"] == {}
    assert payload["green_row_count"] == 0
    assert payload["local_min_ligand_rmsd_a_max"] == 0.0
    assert payload["hbond_persistence_min"] == 0.0
    assert payload["contact_persistence_min"] == 0.0
    assert payload["initial_clash_count_total"] == 0.0
    assert payload["final_clash_count_total"] == 0.0
    assert payload["clash_relief_count_total"] == 0.0
    assert payload["green_band_condition_text"] == ""
    assert payload["top_k_only_policy_enforced"] is False
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
