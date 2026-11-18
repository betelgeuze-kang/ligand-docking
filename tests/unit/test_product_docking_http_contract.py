"""Submission/polling contract on the complete source API with no worker dispatch."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config import settings
from api.product_docking import router
from api.security import ProductSecurityMiddleware


def test_submission_and_status_preserve_scientific_input_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise both authenticated HTTP routes and the persisted job record."""
    from api import docking_dispatch, job_store
    from betelgeuze_product import docking_private_payload

    for name, value in {
        "results_storage_path": str(tmp_path / "results"),
        "product_api_audit_log_path": str(tmp_path / "audit.jsonl"),
        "product_api_auth_required": True,
        "product_api_hosted_exposure_approved": False,
        "product_api_token": "tenant-a-token",
        "product_api_token_tenant_id": "tenant-a",
        "product_api_admin_token": "admin-token",
        "product_api_rate_limit_per_minute": 10000,
        "product_api_tenant_daily_quota": 10000,
        "product_api_max_payload_bytes": 1000000,
    }.items():
        monkeypatch.setattr(settings, name, value)
    headers = {"Authorization": "Bearer tenant-a-token", "X-Tenant-ID": "tenant-a"}
    monkeypatch.setattr(docking_private_payload, "configured_store", lambda: None)
    monkeypatch.setattr(job_store, "get_configured_job_store", lambda: None)
    monkeypatch.setattr(
        docking_dispatch,
        "dispatch_docking_job_if_eligible",
        lambda *args, **kwargs: {"dispatched": False, "reason": "contract_test_no_worker"},
    )
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)
    app.include_router(router)
    client = TestClient(app)
    submitted = client.post(
        "/product/docking/jobs",
        headers=headers,
        json={
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "ligand-a", "smiles": "CCO"}],
            "pocket_center": [0.0, 0.0, 0.0],
            "pocket_radius_a": 6.0,
        },
    )
    assert submitted.status_code == 200, submitted.text
    first = submitted.json()
    polled = client.get(first["links"]["self"], headers=headers)
    assert polled.status_code == 200, polled.text
    current = polled.json()
    assert current["scientific_input"] == first["scientific_input"]
    assert set(current) == set(first)
    assert current["scientific_input"]["explicit_pocket"] is True
    assert current["scientific_input"]["ligand_count"] == 1
    assert current["scientific_input"]["receipt_sha256"]
    assert current["scientific_input"]["claim_safe"] is False
    for document in (first, current):
        encoded = json.dumps(document)
        assert "CCO" not in encoded and "ATOM      1" not in encoded
        assert str(tmp_path) not in encoded
