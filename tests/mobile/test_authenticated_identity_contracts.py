from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from api.config import settings
from api.request_identity import request_identity
from api.security import ProductSecurityMiddleware

pytestmark = pytest.mark.mobile


def _configure_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    auth_required: bool,
) -> None:
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", auth_required)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_tls_termination_operator_verified", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 10_000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 1024)
    monkeypatch.setattr(settings, "product_api_token", "")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "local")
    monkeypatch.setattr(settings, "product_api_admin_token", "")


def _identity_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.get("/product/identity")
    def identity(request: Request) -> dict[str, object]:
        current = request_identity(request)
        return {
            "tenant_id": current.tenant_id,
            "principal": current.principal,
            "authenticated": current.authenticated,
            "is_admin": current.is_admin,
        }

    @app.get("/productevil")
    def deceptive_prefix() -> dict[str, str]:
        return {"status": "must-not-be-reachable"}

    return app


def test_product_token_is_bound_to_server_configured_tenant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_base(monkeypatch, tmp_path, auth_required=True)
    monkeypatch.setattr(settings, "product_api_token", "tenant-token")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "tenant-a")

    client = TestClient(_identity_app())
    without_header = client.get(
        "/product/identity",
        headers={"Authorization": "Bearer tenant-token"},
    )
    matching_header = client.get(
        "/product/identity",
        headers={
            "Authorization": "Bearer tenant-token",
            "X-Tenant-ID": "tenant-a",
        },
    )
    spoofed_header = client.get(
        "/product/identity",
        headers={
            "Authorization": "Bearer tenant-token",
            "X-Tenant-ID": "tenant-b",
        },
    )

    assert without_header.status_code == 200
    assert without_header.json() == {
        "tenant_id": "tenant-a",
        "principal": "token:tenant-a",
        "authenticated": True,
        "is_admin": False,
    }
    assert matching_header.status_code == 200
    assert matching_header.json()["tenant_id"] == "tenant-a"
    assert spoofed_header.status_code == 403
    assert spoofed_header.json()["code"] == "tenant_identity_mismatch"

    rows = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    success_rows = [row for row in rows if row["status_code"] == 200]
    blocked_rows = [row for row in rows if row["status_code"] == 403]
    assert [row["tenant_id"] for row in success_rows] == ["tenant-a", "tenant-a"]
    assert blocked_rows[0]["tenant_id"] == "unauthenticated"
    assert "tenant-token" not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


def test_admin_token_creates_privileged_server_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_base(monkeypatch, tmp_path, auth_required=True)
    monkeypatch.setattr(settings, "product_api_token", "tenant-token")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "tenant-a")
    monkeypatch.setattr(settings, "product_api_admin_token", "admin-token")

    response = TestClient(_identity_app()).get(
        "/product/identity",
        headers={
            "Authorization": "Bearer admin-token",
            "X-Tenant-ID": "attacker-selected-tenant",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "admin",
        "principal": "admin-token",
        "authenticated": True,
        "is_admin": True,
    }


def test_equal_admin_and_product_tokens_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_base(monkeypatch, tmp_path, auth_required=True)
    monkeypatch.setattr(settings, "product_api_token", "same-token")
    monkeypatch.setattr(settings, "product_api_admin_token", "same-token")

    response = TestClient(_identity_app()).get(
        "/product/identity",
        headers={"Authorization": "Bearer same-token"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "server_token_configuration_invalid"


def test_local_tenant_id_is_allowlisted_and_prefix_match_requires_path_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_base(monkeypatch, tmp_path, auth_required=False)
    client = TestClient(_identity_app())

    invalid_tenant = client.get(
        "/product/identity",
        headers={"X-Tenant-ID": "../tenant"},
    )
    deceptive_prefix = client.get("/productevil")

    assert invalid_tenant.status_code == 400
    assert invalid_tenant.json()["code"] == "invalid_tenant_id"
    assert deceptive_prefix.status_code == 404
    assert deceptive_prefix.json()["code"] == "path_not_allowed"


def test_invalid_content_length_fails_closed_before_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_base(monkeypatch, tmp_path, auth_required=False)
    client = TestClient(_identity_app())

    malformed = client.get(
        "/product/identity",
        headers={"Content-Length": "not-an-integer"},
    )
    negative = client.get(
        "/product/identity",
        headers={"Content-Length": "-1"},
    )

    assert malformed.status_code == 400
    assert malformed.json()["code"] == "invalid_content_length"
    assert negative.status_code == 400
    assert negative.json()["code"] == "invalid_content_length"


def test_configured_auth_fails_closed_without_security_middleware(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_base(monkeypatch, tmp_path, auth_required=True)
    request = StarletteRequest(
        {
            "type": "http",
            "method": "GET",
            "path": "/product/identity",
            "headers": [(b"x-tenant-id", b"attacker-selected")],
        }
    )

    with pytest.raises(Exception) as request_exc:
        request_identity(request)
    assert getattr(request_exc.value, "status_code", None) == 401

    with pytest.raises(Exception) as missing_request_exc:
        request_identity(None)
    assert getattr(missing_request_exc.value, "status_code", None) == 401
