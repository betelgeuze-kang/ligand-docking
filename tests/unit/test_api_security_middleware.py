from __future__ import annotations

import json
import sqlite3
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


def test_secure_api_submission_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import api.main as main
    from api.config import settings
    from api.job_store import SQLiteJobStore, reset_configured_job_store_for_tests

    audit_log = tmp_path / "audit.jsonl"
    db_path = tmp_path / "api_jobs.sqlite3"
    results_path = tmp_path / "results"

    monkeypatch.setattr(settings, "api_job_store_path", str(db_path))
    monkeypatch.setattr(settings, "results_storage_path", str(results_path))
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(audit_log))
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_token", "expected-token")
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)
    monkeypatch.setattr(settings, "api_inline_worker_enabled", False)
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "tenant-secure-e2e")

    reset_configured_job_store_for_tests()
    monkeypatch.setattr(main, "job_store", None)
    monkeypatch.setattr(main, "_job_store_path", None)

    client = TestClient(main.app)
    private_payload = {
        "runner_profile_id": "smoke",
        "target_name": "ADRB2",
        "pdb_content": (
            "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"
        ),
        "runner_profile_params": {
            "ligands": ["CCO"],
            "metadata": {"ligand_smiles": "CCN"},
        },
    }
    tenant_headers = {"X-Tenant-ID": "tenant-secure-e2e"}

    missing_auth = client.post("/simulate", json=private_payload, headers=tenant_headers)
    assert missing_auth.status_code == 401
    assert missing_auth.headers["X-Block-Code"] == "auth_required"

    wrong_auth = client.post(
        "/simulate",
        json=private_payload,
        headers={**tenant_headers, "Authorization": "Bearer wrong-token"},
    )
    assert wrong_auth.status_code == 401
    assert wrong_auth.headers["X-Block-Code"] == "auth_required"

    accepted = client.post(
        "/simulate",
        json=private_payload,
        headers={**tenant_headers, "Authorization": "Bearer expected-token"},
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["status"] == "submitted"
    assert body["job_id"]
    assert accepted.headers["X-Content-Type-Options"] == "nosniff"
    assert accepted.headers["X-Frame-Options"] == "DENY"
    assert accepted.headers["Referrer-Policy"] == "no-referrer"

    job_id = body["job_id"]
    store = SQLiteJobStore(db_path)
    record = store.get_job(job_id)
    assert record is not None
    assert record["status"] == "submitted"
    assert record["worker_id"] == ""
    assert record["attempt_count"] == 0
    assert record["request"]["target_name"] == "ADRB2"
    assert record["request"]["pdb_content"]["redacted"] is True
    assert record["request"]["runner_profile_params"]["ligands"][0]["redacted"] is True
    assert record["request"]["runner_profile_params"]["metadata"]["ligand_smiles"]["redacted"] is True

    with sqlite3.connect(db_path) as conn:
        raw_request = conn.execute(
            "SELECT request_json FROM simulation_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()[0]
    assert "ATOM      1" not in raw_request
    assert "CCO" not in raw_request
    assert "CCN" not in raw_request
    assert "sha256" in raw_request
    assert "redacted" in raw_request

    status_path = results_path / job_id / "status.json"
    assert status_path.exists()
    status_data = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_data == {"job_id": job_id, "status": "submitted"}

    pending = store.list_pending_outbox_events()
    created_events = [
        event for event in pending if event["job_id"] == job_id and event["event_type"] == "job_created"
    ]
    assert len(created_events) == 1
    payload_json = json.dumps(created_events[0]["payload"], sort_keys=True)
    assert "ATOM      1" not in payload_json
    assert "CCO" not in payload_json
    assert "CCN" not in payload_json
    assert created_events[0]["payload"]["target_name"] == "ADRB2"

    audit_text = audit_log.read_text(encoding="utf-8")
    assert "expected-token" not in audit_text
    assert "wrong-token" not in audit_text
    assert "ATOM      1" not in audit_text
    assert "CCO" not in audit_text
    assert "CCN" not in audit_text

    audit_rows = [json.loads(line) for line in audit_text.strip().splitlines() if line.strip()]
    blocked_rows = [row for row in audit_rows if row["path"] == "/simulate" and row["status_code"] == 401]
    assert len(blocked_rows) == 2
    for row in blocked_rows:
        # A caller-supplied tenant header is not trusted until authentication
        # succeeds, so failed authentication is audited without tenant binding.
        assert row["tenant_id"] == "unauthenticated"
        assert row["request_body_logged"] is False
        assert row["authorization_value_logged"] is False

    success_rows = [row for row in audit_rows if row["path"] == "/simulate" and row["status_code"] == 200]
    assert len(success_rows) == 1
    assert success_rows[0]["authorization_present"] is True
    assert success_rows[0]["request_body_logged"] is False
    assert success_rows[0]["authorization_value_logged"] is False
