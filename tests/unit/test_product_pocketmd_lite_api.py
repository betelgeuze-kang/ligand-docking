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
                    "missing_refinement_metric_names": ["hbond_persistence"],
                    "missing_refinement_metric_counts": {"hbond_persistence": 5},
                    "claim_promotion_allowed": False,
                },
                "rows": [{"entry_id": "ADRB2.compound_001"}],
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
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
    assert payload["rows"] == [{"entry_id": "ADRB2.compound_001"}]


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
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False
