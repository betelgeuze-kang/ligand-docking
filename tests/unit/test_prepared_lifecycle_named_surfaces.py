"""Named CLI/HTTP metadata contracts; no owner, evaluator or native runner calls."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import product_prepared
from api.config import settings
from api.security import ProductSecurityMiddleware
from betelgeuze_product import docking_cli, prepared_lifecycle as lifecycle


@pytest.fixture
def registered(monkeypatch, tmp_path):
    """Byte-admitted synthetic metadata, deliberately not valid molecular input."""
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    bundle = inputs / "named-synthetic"
    bundle.mkdir(mode=0o700)
    protocol = {
        "schema_version": "prepared_fourier_development_protocol/1.0.0",
        "evidence_kind": "synthetic_control",
        "solver": {"minimization": {"max_iterations": 4, "max_backtracks": 3}},
    }
    for role in lifecycle.REFS:
        path = bundle / (role + ".json")
        value = {"source_files": []} if role == "source_evidence" else {"metadata_only": role}
        raw = lifecycle.canonical(value).encode()
        path.write_bytes(raw)
        protocol[role] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    protocol_path = bundle / "protocol.json"
    protocol_path.write_text(lifecycle.canonical(protocol))
    lifecycle.register_admission(inputs, bundle.name, protocol_path, tenant_id="local")
    configuration = {
        "ENABLED": "1", "STATE_ROOT": str(tmp_path / "state"),
        "INPUT_ROOT": str(inputs), "TENANT_ID": "local",
    }
    for name, value in configuration.items():
        monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_" + name, value)
    owner_calls = []
    owner = types.ModuleType("betelgeuze_product.prepared_lifecycle_owner")

    def forbidden_owner(*args, **kwargs):
        owner_calls.append((args, kwargs))
        raise AssertionError("A named metadata operation must not invoke an owner")

    owner.run_one = forbidden_owner
    monkeypatch.setitem(sys.modules, owner.__name__, owner)
    return {"bundle": bundle, "tmp_path": tmp_path, "owner_calls": owner_calls}


@pytest.fixture
def authenticated(monkeypatch, tmp_path):
    """Use the existing security middleware, rather than inject a principal."""
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_token", "named-surface-test-token")
    monkeypatch.setattr(settings, "product_api_admin_token", "")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "local")
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "http-audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_security_ledger_path", str(tmp_path / "http-security.sqlite3"))
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 5000)
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)
    app.include_router(product_prepared.router, prefix="/product")
    with TestClient(app) as client:
        yield client, {"Authorization": "Bearer named-surface-test-token"}


def cli_json(capsys, *arguments):
    assert docking_cli.main(["prepared-jobs", *arguments]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_cli_plan_http_execute_and_cli_replay_share_one_unstarted_registry(
    registered, authenticated, capsys,
):
    client, headers = authenticated
    planned = cli_json(capsys, "plan", registered["bundle"].name)
    service = lifecycle.configured_service()
    with service._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM prepared_jobs").fetchone()[0] == 0
    body = {
        "plan_id": planned["plan_id"], "plan_sha256": planned["plan_sha256"],
        "idempotency_key": "named:shared-key",
    }
    response = client.post("/product/prepared/jobs/execute", headers=headers, json=body)
    assert response.status_code == 202
    first = response.json()
    assert first["status"] == "queued"
    again_http = client.post("/product/prepared/jobs/execute", headers=headers, json=body)
    assert again_http.status_code == 202
    replay = cli_json(
        capsys, "execute", planned["plan_id"], "--plan-sha256", planned["plan_sha256"],
        "--idempotency-key", "named:shared-key",
    )
    assert first == again_http.json() == replay
    assert first["budget"]["numerical_invocations"] == 0
    assert first["budget"]["total_force_calls"] == 0
    assert first["budget"]["total_work_known"] is True
    with service._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM prepared_jobs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM prepared_execution_plans").fetchone()[0] == 1
        kinds = [row[0] for row in connection.execute("SELECT kind FROM prepared_events ORDER BY rowid")]
    assert kinds == ["submitted", "plan_bound"]
    assert registered["owner_calls"] == []
    assert list((service.root / "jobs" / first["execution_id"]).glob("attempts/*")) == []


def test_public_plan_hides_paths_and_actual_token_tenant_is_authoritative(
    registered, authenticated, monkeypatch, capsys,
):
    client, headers = authenticated
    plan = cli_json(capsys, "plan", registered["bundle"].name)
    response = client.get("/product/prepared/jobs/plans/" + plan["plan_id"], headers=headers)
    assert response.status_code == 200
    assert response.json() == cli_json(capsys, "get-plan", plan["plan_id"]) == plan
    assert str(registered["tmp_path"]) not in json.dumps(plan)
    assert plan["preflight"]["numerical_dispatches"] == plan["preflight"]["force_calls"] == 0
    assert plan["qualified"] is False and plan["research_only"] is True
    # Trusted CLI defaults never override the authenticated HTTP principal.
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_TENANT_ID", "other:tenant")
    assert client.get("/product/prepared/jobs/plans/" + plan["plan_id"], headers=headers).json() == plan
    # Changing the token's server-side binding gives a genuinely foreign principal.
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "other:tenant")
    for method, path, body in [
        ("get", "/product/prepared/jobs/plans/" + plan["plan_id"], None),
        ("post", "/product/prepared/jobs/plans", {"admission_id": registered["bundle"].name}),
        ("post", "/product/prepared/jobs/execute", {
            "plan_id": plan["plan_id"], "plan_sha256": plan["plan_sha256"],
            "idempotency_key": "foreign:attempt",
        }),
    ]:
        response = client.request(method, path, headers=headers, json=body)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND_OR_FORBIDDEN"
        assert str(registered["tmp_path"]) not in response.text
    assert registered["owner_calls"] == []
    with lifecycle.configured_service(tenant_id="local")._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM prepared_jobs").fetchone()[0] == 0


def test_http_execute_rejects_wrong_digest_without_enqueuing(registered, authenticated, capsys):
    client, headers = authenticated
    plan = cli_json(capsys, "plan", registered["bundle"].name)
    response = client.post("/product/prepared/jobs/execute", headers=headers, json={
        "plan_id": plan["plan_id"], "plan_sha256": "0" * 64, "idempotency_key": "bad:digest",
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAN_INTEGRITY_FAILED"
    with lifecycle.configured_service()._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM prepared_jobs").fetchone()[0] == 0
    assert registered["owner_calls"] == []


@pytest.fixture
def named_facade(monkeypatch):
    class Facade:
        def __init__(self):
            self.calls = []

        def record(self, action, *args, **kwargs):
            self.calls.append((action, args, kwargs))
            return {"operation": action, "research_only": True, "qualified": False}

        def verify(self, *args, **kwargs):
            return self.record("verify", *args, **kwargs)

        def report(self, *args, **kwargs):
            return self.record("report", *args, **kwargs)

        def compare(self, *args, **kwargs):
            return self.record("compare", *args, **kwargs)

    facade = Facade()
    construction = []

    def factory(**kwargs):
        construction.append(kwargs)
        return facade

    monkeypatch.setattr(lifecycle, "configured_service", factory)
    return facade, construction


@pytest.mark.parametrize("operation", ["verify", "report", "compare"])
def test_named_results_delegate_through_the_same_cli_http_facade(
    named_facade, authenticated, capsys, operation,
):
    facade, construction = named_facade
    client, headers = authenticated
    ids = ["a" * 32, "b" * 32] if operation == "compare" else ["a" * 32]
    expected = (ids,) if operation == "compare" else (ids[0],)
    cli = cli_json(capsys, operation, *ids)
    response = (
        client.post("/product/prepared/jobs/compare", headers=headers, json={"execution_ids": ids})
        if operation == "compare" else
        client.get("/product/prepared/jobs/" + ids[0] + "/" + operation, headers=headers)
    )
    assert response.status_code == 200
    assert response.json() == cli
    assert facade.calls == [(operation, expected, {}), (operation, expected, {})]
    assert construction == [{}, {"tenant_id": "local"}]


@pytest.mark.parametrize("operation", ["verify", "report", "compare"])
def test_named_results_preserve_injected_typed_refusal_across_surfaces(
    named_facade, authenticated, monkeypatch, capsys, operation,
):
    facade, _ = named_facade
    client, headers = authenticated

    def refused(*args, **kwargs):
        raise lifecycle.LifecycleError("UNKNOWN_WORK", "Retained work is uncertain", http_status=409)

    monkeypatch.setattr(facade, operation, refused)
    assert docking_cli.main(["prepared-jobs", operation, "a" * 32]) == 2
    cli_error = json.loads(capsys.readouterr().err)
    response = (
        client.post("/product/prepared/jobs/compare", headers=headers, json={"execution_ids": ["a" * 32]})
        if operation == "compare" else
        client.get("/product/prepared/jobs/" + "a" * 32 + "/" + operation, headers=headers)
    )
    assert response.status_code == 409
    assert response.json() == cli_error
    assert cli_error["error"] == {
        "code": "UNKNOWN_WORK", "message": "Retained work is uncertain", "retry_allowed": False,
    }


@pytest.mark.parametrize("method,path,body", [
    ("post", "/product/prepared/jobs/plans", {"admission_id": "registered"}),
    ("get", "/product/prepared/jobs/plans/" + "a" * 32, None),
    ("post", "/product/prepared/jobs/execute", {
        "plan_id": "a" * 32, "plan_sha256": "b" * 64, "idempotency_key": "key",
    }),
    ("post", "/product/prepared/jobs/compare", {"execution_ids": ["a" * 32]}),
])
def test_named_http_requires_actual_authentication_before_facade(
    named_facade, authenticated, method, path, body,
):
    facade, construction = named_facade
    client, _ = authenticated
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert facade.calls == [] and construction == []


@pytest.mark.parametrize("operation,body,field,value", [
    ("plans", {"admission_id": "registered"}, "protocol", "/secret/protocol.json"),
    ("plans", {"admission_id": "registered"}, "env", {"TOKEN": "secret"}),
    ("execute", {"plan_id": "a" * 32, "plan_sha256": "b" * 64, "idempotency_key": "key"},
     "argv", ["untrusted-program"]),
    ("execute", {"plan_id": "a" * 32, "plan_sha256": "b" * 64, "idempotency_key": "key"},
     "tenant_id", "other:tenant"),
    ("compare", {"execution_ids": ["a" * 32]}, "model", "different-model"),
    ("compare", {"execution_ids": ["a" * 32]}, "output", "/secret/report.json"),
])
def test_named_http_rejects_extra_controls_before_constructing_facade(
    named_facade, authenticated, operation, body, field, value,
):
    facade, construction = named_facade
    client, headers = authenticated
    response = client.post("/product/prepared/jobs/" + operation, headers=headers, json={**body, field: value})
    assert response.status_code == 422
    assert facade.calls == [] and construction == []


@pytest.mark.parametrize("arguments", [
    ["plan", "registered", "--protocol", "/secret/protocol.json"],
    ["plan", "registered", "--tenant-id", "other:tenant"],
    ["execute", "a" * 32, "--plan-sha256", "b" * 64, "--idempotency-key", "key",
     "--argv", "untrusted-program"],
    ["execute", "a" * 32, "--plan-sha256", "b" * 64, "--idempotency-key", "key",
     "--env", "TOKEN=secret"],
    ["compare", "a" * 32, "--output", "/secret/report.json"],
])
def test_named_cli_rejects_unsafe_controls_without_echoing_values(named_facade, capsys, arguments):
    facade, construction = named_facade
    assert docking_cli.main(["prepared-jobs", *arguments]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err)["error"]["code"] == "INVALID_ARGUMENT"
    assert "secret" not in captured.err and "untrusted-program" not in captured.err
    assert facade.calls == [] and construction == []


def test_base_help_and_real_byte_only_plan_import_no_numerical_or_http_dependencies(registered):
    root = Path(__file__).resolve().parents[2]
    script = """
import builtins, json, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'numpy', 'fastapi', 'starlette', 'pydantic', 'api', 'betelgeuze_engine_v2'}:
        raise AssertionError('forbidden dependency import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from betelgeuze_product.docking_cli import main
try:
    main(['prepared-jobs', '--help'])
except SystemExit as exc:
    assert exc.code == 0
assert main(['prepared-jobs', 'plan', sys.argv[2]]) == 0
"""
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("BETELGEUZE_PREPARED_LIFECYCLE_")
    }
    environment.update({
        "BETELGEUZE_PREPARED_LIFECYCLE_ENABLED": "1",
        "BETELGEUZE_PREPARED_LIFECYCLE_STATE_ROOT": str(registered["tmp_path"] / "isolated-state"),
        "BETELGEUZE_PREPARED_LIFECYCLE_INPUT_ROOT": str(registered["bundle"].parent),
        "BETELGEUZE_PREPARED_LIFECYCLE_TENANT_ID": "local",
    })
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(root), registered["bundle"].name],
        cwd=registered["tmp_path"], env=environment, capture_output=True, text=True,
        check=False, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    plan = json.loads(result.stdout.splitlines()[-1])
    assert plan["preflight"]["force_calls"] == 0
    assert str(registered["tmp_path"]) not in json.dumps(plan)
