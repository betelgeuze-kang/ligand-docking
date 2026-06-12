from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_product_security_middleware_audits_blocked_requests_and_sets_headers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.config import settings
    from api.security import ProductSecurityMiddleware

    audit_log = tmp_path / "audit.jsonl"
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(audit_log))
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 1024)
    monkeypatch.setattr(settings, "product_api_audit_retention_days", 90)

    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/product/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/not-allowed", headers={"Authorization": "Bearer super-secret", "X-Tenant-ID": "tenant-a"})

    assert response.status_code == 404
    assert response.json()["code"] == "path_not_allowed"
    assert response.json()["execution_enabled"] is False
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

    audit_row = json.loads(audit_log.read_text(encoding="utf-8").strip())
    assert audit_row["path"] == "/not-allowed"
    assert audit_row["status_code"] == 404
    assert audit_row["tenant_id"] == "tenant-a"
    assert audit_row["authorization_present"] is True
    assert audit_row["request_body_logged"] is False
    assert audit_row["authorization_value_logged"] is False
    assert audit_row["audit_retention_days"] == 90
    assert "super-secret" not in audit_log.read_text(encoding="utf-8")


def test_product_security_middleware_sets_headers_on_allowed_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.config import settings
    from api.security import ProductSecurityMiddleware

    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)

    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/product/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(app).get("/product/ping", headers={"X-Tenant-ID": "tenant-b"})

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_metrics_endpoint_is_secret_free_and_exposes_runtime_counters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    from fastapi.testclient import TestClient

    from api.config import settings
    from api.security import ProductSecurityMiddleware, security_metrics_text

    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_token", "expected-token")
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)

    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return security_metrics_text()

    client = TestClient(app)

    blocked = client.get("/not-allowed")
    assert blocked.status_code == 404
    assert blocked.headers["X-Block-Code"] == "path_not_allowed"

    client.get("/metrics")
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    text = metrics_response.text
    assert "betelgeuze_product_security_controls" in text
    assert "betelgeuze_product_http_requests_total" in text
    assert "betelgeuze_product_blocked_requests_total" in text
    assert 'blocked_code="path_not_allowed"' in text
    assert 'code="path_not_allowed"' in text
    assert 'path="/metrics"' in text


def test_hosted_exposure_requires_operator_verified_tls_except_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    from fastapi.testclient import TestClient

    from api.config import settings
    from api.security import ProductSecurityMiddleware, security_metrics_text

    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", True)
    monkeypatch.setattr(settings, "product_api_tls_termination_operator_verified", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)

    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/product/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return security_metrics_text()

    client = TestClient(app)

    blocked = client.get("/product/ping")
    assert blocked.status_code == 503
    assert blocked.json()["code"] == "hosted_tls_termination_not_verified"
    assert blocked.headers["X-Block-Code"] == "hosted_tls_termination_not_verified"

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200

    monkeypatch.setattr(settings, "product_api_tls_termination_operator_verified", True)
    allowed = client.get("/product/ping")
    assert allowed.status_code == 200


def test_product_security_middleware_blocks_tenant_quota(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.config import settings
    from api.security import ProductSecurityMiddleware

    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 1)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 1024)

    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/product/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    first = client.get("/product/ping", headers={"X-Tenant-ID": "tenant-quota"})
    second = client.get("/product/ping", headers={"X-Tenant-ID": "tenant-quota"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "tenant_quota_exceeded"
    assert second.headers["X-Block-Code"] == "tenant_quota_exceeded"
