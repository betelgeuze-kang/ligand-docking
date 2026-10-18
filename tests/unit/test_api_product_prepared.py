from __future__ import annotations

import hashlib
import json

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import product_prepared
from api.request_identity import ProductRequestIdentity
from betelgeuze_product import prepared_lifecycle as lifecycle


@pytest.fixture
def service(monkeypatch, tmp_path):
    class FakeFacade:
        def __init__(self):
            self.calls = []

        def _record(self, action, *args, **kwargs):
            self.calls.append((action, args, kwargs))
            return {
                "execution_id": "a" * 32, "status": "queued", "numerical_state": "not_started",
                "cancel_state": "requested" if action == "cancel" else "none",
                "research_only": True, "qualified": False,
            }

        def submit(self, *args, **kwargs):
            return self._record("submit", *args, **kwargs)

        def status(self, *args, **kwargs):
            return self._record("status", *args, **kwargs)

        def cancel(self, *args, **kwargs):
            return self._record("cancel", *args, **kwargs)

        def resume(self, *args, **kwargs):
            return self._record("resume", *args, **kwargs)

        def artifacts(self, *args, **kwargs):
            return self._record("artifacts", *args, **kwargs)

        def artifact(self, *args, **kwargs):
            self._record("artifact", *args, **kwargs)
            path = tmp_path / "private-report.json"
            path.write_bytes(b'{"research_only":true}\n')
            return path, {
                "artifact_id": "b" * 32, "role": "report", "schema": "test/1",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size, "media_type": "application/json",
            }

    facade = FakeFacade()
    tenants = []

    def factory(*, tenant_id):
        tenants.append(tenant_id)
        return facade

    monkeypatch.setattr(lifecycle, "configured_service", factory)
    return facade, tenants


def client_for(identity=None):
    app = FastAPI()
    if identity is not None:
        @app.middleware("http")
        async def authenticated_principal(request, call_next):
            request.state.product_identity = identity
            return await call_next(request)
    app.include_router(product_prepared.router, prefix="/product")
    return TestClient(app)


def authenticated_client():
    return client_for(ProductRequestIdentity(
        tenant_id="bound-tenant", principal="token:bound-tenant", authenticated=True,
    ))


@pytest.mark.parametrize("identity", [
    None,
    ProductRequestIdentity(tenant_id="attacker", principal="local:attacker", authenticated=False),
])
def test_http_never_uses_raw_tenant_header_as_identity(service, identity):
    facade, tenants = service
    response = client_for(identity).get(
        "/product/prepared/jobs/" + "a" * 32, headers={"X-Tenant-ID": "attacker"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert facade.calls == []
    assert tenants == []


def test_existing_security_middleware_binds_token_tenant(service, monkeypatch, tmp_path):
    from api.config import settings
    from api.security import ProductSecurityMiddleware

    _, tenants = service
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_token", "synthetic-test-token")
    monkeypatch.setattr(settings, "product_api_admin_token", "")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "trusted:tenant")
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_security_ledger_path", str(tmp_path / "security.sqlite3"))
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)
    app.include_router(product_prepared.router, prefix="/product")
    client = TestClient(app)
    path = "/product/prepared/jobs/" + "a" * 32

    assert client.get(path).status_code == 401
    assert client.get(path, headers={
        "Authorization": "Bearer synthetic-test-token", "X-Tenant-ID": "other",
    }).status_code == 403
    assert tenants == []
    response = client.get(path, headers={"Authorization": "Bearer synthetic-test-token"})
    assert response.status_code == 200
    assert tenants == ["trusted:tenant"]


def test_authenticated_submit_queues_same_facade_with_bound_tenant(service):
    facade, tenants = service
    response = authenticated_client().post(
        "/product/prepared/jobs", headers={"X-Tenant-ID": "other-tenant"},
        json={"admission_id": "admitted", "idempotency_key": "public:key"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["qualified"] is False
    assert facade.calls == [("submit", ("admitted", "public:key"), {"budget_policy": "local_cpu_research_v1"})]
    assert tenants == ["bound-tenant"]


@pytest.mark.parametrize("field,value", [
    ("protocol", "/private/protocol.json"), ("run_dir", "/private/run"),
    ("argv", ["untrusted-program"]), ("env", {"SECRET": "value"}),
    ("profile", "unbounded"), ("tenant_id", "other-tenant"), ("max_force_calls", 999),
])
def test_http_rejects_unregistered_controls_before_facade(service, field, value):
    facade, tenants = service
    response = authenticated_client().post("/product/prepared/jobs", json={
        "admission_id": "admitted", "idempotency_key": "key", field: value,
    })
    assert response.status_code == 422
    assert facade.calls == []
    assert tenants == []


def test_http_cancel_202_is_only_requested(service):
    facade, _ = service
    response = authenticated_client().post(
        "/product/prepared/jobs/" + "a" * 32 + "/cancel", json={"reason": "stop requested"},
    )
    assert response.status_code == 202
    assert response.json()["cancel_state"] == "requested"
    assert response.json()["status"] == "queued"
    assert facade.calls == [("cancel", ("a" * 32,), {"reason": "stop requested"})]


@pytest.mark.parametrize("action", ["status", "resume", "artifacts"])
def test_http_lifecycle_queries_use_same_facade(service, action):
    facade, tenants = service
    path = "/product/prepared/jobs/" + "a" * 32
    if action != "status":
        path += "/" + action
    client = authenticated_client()
    response = client.post(path) if action == "resume" else client.get(path)
    assert response.status_code == (202 if action == "resume" else 200)
    assert facade.calls == [(action, ("a" * 32,), {})]
    assert tenants == ["bound-tenant"]


def test_http_preserves_unknown_resume_and_cross_tenant_refusals(service, monkeypatch):
    facade, _ = service

    def refused(execution_id):
        raise lifecycle.LifecycleError("UNKNOWN_WORK", "Unknown work cannot be resumed", http_status=409)

    monkeypatch.setattr(facade, "resume", refused)
    response = authenticated_client().post("/product/prepared/jobs/" + "a" * 32 + "/resume")
    assert response.status_code == 409
    assert response.json()["error"]["retry_allowed"] is False
    assert response.json()["error"]["code"] == "UNKNOWN_WORK"

    def hidden(execution_id):
        raise lifecycle.LifecycleError("NOT_FOUND", "Execution not found", http_status=404)

    monkeypatch.setattr(facade, "status", hidden)
    response = authenticated_client().get("/product/prepared/jobs/" + "a" * 32)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_http_download_uses_only_facade_checked_artifact(service):
    facade, _ = service
    response = authenticated_client().get(
        "/product/prepared/jobs/" + "a" * 32 + "/artifacts/" + "b" * 32,
    )
    assert response.status_code == 200
    assert response.content == b'{"research_only":true}\n'
    assert response.headers["etag"] == '"' + hashlib.sha256(response.content).hexdigest() + '"'
    assert "private-report" not in response.headers["content-disposition"]
    assert facade.calls == [("artifact", ("a" * 32, "b" * 32), {})]


def test_http_internal_failure_is_sanitized(service, monkeypatch):
    facade, _ = service

    def failed(execution_id):
        raise RuntimeError("private /secret/root token=credential")

    monkeypatch.setattr(facade, "status", failed)
    response = authenticated_client().get("/product/prepared/jobs/" + "a" * 32)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text
    assert "credential" not in response.text


def test_authenticated_http_defaults_disabled_without_configuration(monkeypatch):
    for key in (
        "BETELGEUZE_PREPARED_LIFECYCLE_ENABLED", "BETELGEUZE_PREPARED_LIFECYCLE_STATE_ROOT",
        "BETELGEUZE_PREPARED_LIFECYCLE_INPUT_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)
    response = authenticated_client().get("/product/prepared/jobs/" + "a" * 32)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LIFECYCLE_DISABLED"
    assert response.json()["qualified"] is False


def test_prepared_router_is_in_existing_product_router():
    from api.product import router

    routes = {(route.path, method) for route in router.routes for method in route.methods}
    assert ("/product/prepared/jobs", "POST") in routes
    assert ("/product/prepared/jobs/{execution_id}/artifacts/{artifact_id}", "GET") in routes
    assert all("owner-once" not in path for path, _ in routes)


def test_cli_and_http_share_durable_idempotency_and_tenant_isolation(monkeypatch, tmp_path, capsys):
    """Queue-only synthetic data: no numerical workflow or physical evaluator."""
    from betelgeuze_product import docking_cli

    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    bundle = inputs / "synthetic-admission"
    bundle.mkdir(mode=0o700)
    protocol = {
        "schema_version": "prepared_fourier_development_protocol/1.0.0",
        "evidence_kind": "synthetic_control",
        "solver": {"minimization": {"max_iterations": 4, "max_backtracks": 3}},
    }
    for role in lifecycle.REFS:
        path = bundle / (role + ".json")
        path.write_text(json.dumps({"source_files": []} if role == "source_evidence" else {"synthetic": role}))
        protocol[role] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    protocol_path = bundle / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    lifecycle.register_admission(inputs, bundle.name, protocol_path)
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_ENABLED", "1")
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_INPUT_ROOT", str(inputs))
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_TENANT_ID", "local")

    assert docking_cli.main([
        "prepared-jobs", "submit", bundle.name, "--idempotency-key", "shared:key",
    ]) == 0
    from_cli = json.loads(capsys.readouterr().out)
    local = client_for(ProductRequestIdentity("local", "token:local", True))
    response = local.post("/product/prepared/jobs", json={
        "admission_id": bundle.name, "idempotency_key": "shared:key",
    })
    assert response.status_code == 202
    from_http = response.json()
    assert from_http["execution_id"] == from_cli["execution_id"]
    assert from_http["status"] == "queued"
    assert from_http["budget"]["numerical_invocations"] == 0
    assert from_http["budget"]["total_force_calls"] == 0
    assert from_http["budget"]["total_work_known"] is True
    other = client_for(ProductRequestIdentity("other:tenant", "token:other:tenant", True))
    hidden = other.get("/product/prepared/jobs/" + from_cli["execution_id"])
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "NOT_FOUND_OR_FORBIDDEN"

    # Knowing another tenant's admission ID does not authorize using its files.
    forbidden = other.post("/product/prepared/jobs", json={
        "admission_id": bundle.name, "idempotency_key": "stolen-admission",
    })
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "NOT_FOUND_OR_FORBIDDEN"
    service = lifecycle.configured_service(tenant_id="local")
    with service._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM prepared_jobs").fetchone()[0] == 1

    # HTTP's explicit authenticated tenant overrides the administrator's CLI
    # default tenant, preserving the same original local execution and key.
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_TENANT_ID", "other:tenant")
    replay = local.post("/product/prepared/jobs", json={
        "admission_id": bundle.name, "idempotency_key": "shared:key",
    })
    assert replay.status_code == 202
    assert replay.json()["execution_id"] == from_cli["execution_id"]
