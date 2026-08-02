from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.config import settings
from api.engine_v2_shadow import router
from api.job_store import reset_configured_job_store_for_tests
from api.security import ProductSecurityMiddleware


pytestmark = pytest.mark.mobile


def _app() -> FastAPI:
    assert router is not None
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)
    app.include_router(router)
    return app


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(
        settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl")
    )
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_token", "tenant-token")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "tenant-a")
    monkeypatch.setattr(settings, "product_api_admin_token", "admin-token")
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 10_000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 1_000_000)
    reset_configured_job_store_for_tests()


def test_shadow_route_resolves_request_and_remains_admin_server_owned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure(monkeypatch, tmp_path)
    app = _app()
    schema = app.openapi()
    operation = schema["paths"]["/product/engine-v2/shadow/{job_id}/{receipt_sha256}"][
        "get"
    ]
    parameter_names = {item["name"] for item in operation["parameters"]}
    assert parameter_names == {"job_id", "receipt_sha256"}

    client = TestClient(app)
    path = f"/product/engine-v2/shadow/missing-job/{'a' * 64}"
    assert client.get(path).status_code == 401
    assert (
        client.get(
            path,
            headers={
                "Authorization": "Bearer tenant-token",
                "X-Tenant-ID": "tenant-a",
            },
        ).status_code
        == 403
    )
    assert (
        client.get(
            path,
            headers={"Authorization": "Bearer admin-token"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/product/engine-v2/shadow/missing-job/{'A' * 64}",
            headers={"Authorization": "Bearer admin-token"},
        ).status_code
        == 404
    )
