from __future__ import annotations

import asyncio
import json
from pathlib import Path

from api import product_capabilities as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_product_capabilities_returns_dashboard_safe_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = tmp_path / "runs/product_capability_surface_contract_current.json"
    monkeypatch.setattr(mod, "PRODUCT_CAPABILITY_ARTIFACT", artifact)
    _write_json(
        artifact,
        {
            "summary": {
                "status": "product_capability_surface_contract_ready",
                "target_id": "ADRB2",
                "family": "gpcr",
                "ligand_count": 3,
                "capability_count": 1,
                "ready_capability_count": 0,
                "blocked_capability_count": 1,
                "allowed_scope_families": ["gpcr"],
                "restricted_scope_claim_guard_ready": True,
                "blocked_claim_scopes": ["general_protein_ligand_platform"],
                "general_platform_claim_allowed": False,
                "scope_claim_boundary_detail": "general_platform_claim_allowed=False",
                "evidence_surface_count": 1,
                "claim_boundary": "capability fixture boundary",
            },
            "rows": [
                {
                    "capability_id": "customer_api_bundle",
                    "domain": "api",
                    "status": "blocked",
                    "required": "bundle validation artifacts",
                    "release_blocker": True,
                    "artifact_path": "runs/api_customer_flow_release_evidence_current.json",
                    "observed": "bundle_validation=False",
                    "reason": "Bundle validation evidence missing.",
                    "bundle_assembled": True,
                    "docking_results_emitted": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
            "evidence_surfaces": [
                {
                    "capability_id": "public_benchmark_scorecard",
                    "surface": "product_evidence_surface",
                    "route": "/product/public-benchmark-external-receipts-audit",
                    "artifact": "runs/public_benchmark_external_receipts_audit_current.json",
                    "artifact_present": True,
                    "surface_available": True,
                    "claim_type": "external_benchmark_receipt",
                    "claim_status": "claim_locked_external_receipts_missing",
                    "claim_safe": False,
                    "bundle_surfaces": ["local_delivery_bundle"],
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )

    response = asyncio.run(mod.get_product_capabilities())

    assert response["status"] == "product_capability_surface_contract_ready"
    assert response["capability_row_count"] == 1
    assert response["capability_blocker_row_count"] == 1
    assert response["capabilities"] == response["capability_rows"]
    assert response["capability_rows"] == [
        {
            "capability_id": "customer_api_bundle",
            "domain": "api",
            "status": "blocked",
            "required": "bundle validation artifacts",
            "release_blocker": True,
            "artifact_path": "runs/api_customer_flow_release_evidence_current.json",
            "observed": "bundle_validation=False",
            "reason": "Bundle validation evidence missing.",
            "bundle_assembled": True,
            "docking_results_emitted": False,
            "claim_boundary": "capability fixture boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert response["evidence_surface_row_count"] == 1
    assert response["evidence_surface_claim_locked_row_count"] == 1
    assert response["evidence_surfaces"][0]["execution_enabled"] is False
    assert response["evidence_surfaces"][0]["external_state_mutated"] is False
    assert response["evidence_surfaces"][0]["claim_promotion_allowed"] is False
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False


def test_product_capabilities_missing_artifact_keeps_dashboard_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "PRODUCT_CAPABILITY_ARTIFACT",
        tmp_path / "runs/missing_product_capability_surface_contract_current.json",
    )

    response = asyncio.run(mod.get_product_capabilities())

    assert response["status"] == "missing_product_capability_surface_contract"
    assert response["capability_row_count"] == 0
    assert response["capability_blocker_row_count"] == 0
    assert response["capability_rows"] == []
    assert response["capabilities"] == []
    assert response["evidence_surface_row_count"] == 0
    assert response["evidence_surface_claim_locked_row_count"] == 0
    assert response["evidence_surfaces"] == []
    assert response["execution_enabled"] is False
    assert response["docking_results_emitted"] is False
    assert response["external_state_mutated"] is False
