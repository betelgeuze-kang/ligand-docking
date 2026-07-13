from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config import settings
from api.job_store import SQLiteJobStore
from api.security import ProductSecurityMiddleware

pytestmark = pytest.mark.mobile


def _security_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/product/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_security_middleware_blocks_unknown_paths_and_redacts_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(audit_path))
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 1024)

    response = TestClient(_security_app()).get(
        "/outside-product-scope",
        headers={
            "Authorization": "Bearer mobile-secret-must-not-leak",
            "X-Tenant-ID": "tenant-mobile",
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "path_not_allowed"
    assert response.json()["execution_enabled"] is False
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    audit_text = audit_path.read_text(encoding="utf-8")
    audit_row = json.loads(audit_text.strip())
    assert audit_row["tenant_id"] == "tenant-mobile"
    assert audit_row["authorization_present"] is True
    assert audit_row["authorization_value_logged"] is False
    assert "mobile-secret-must-not-leak" not in audit_text


def test_security_middleware_rejects_oversized_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 4)

    response = TestClient(_security_app()).get(
        "/product/ping",
        headers={"Content-Length": "5", "X-Tenant-ID": "tenant-mobile"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
    assert response.headers["X-Block-Code"] == "payload_too_large"


def test_sqlite_outbox_excludes_private_structure_and_ligand_material(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "mobile_jobs.sqlite3")
    private_request = {
        "target_name": "ADRB2",
        "pdb_content": "ATOM PRIVATE MOBILE FIXTURE",
        "runner_profile_params": {
            "ligands": ["CCO"],
            "metadata": {"ligand_smiles": "CCN"},
        },
    }

    store.create_job("mobile_job_1", private_request, status="submitted")
    pending = store.list_pending_outbox_events()

    assert len(pending) == 1
    serialized = json.dumps(pending[0]["payload"], sort_keys=True)
    assert pending[0]["payload"]["target_name"] == "ADRB2"
    assert "ATOM PRIVATE MOBILE FIXTURE" not in serialized
    assert "CCO" not in serialized
    assert "CCN" not in serialized
    assert "pdb_content" not in serialized
    assert "runner_profile_params" not in serialized
