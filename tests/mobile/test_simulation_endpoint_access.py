from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from api.config import settings
from api.job_store import SQLiteJobStore
from api.request_identity import ProductRequestIdentity
from api.simulation_endpoint_access import (
    create_simulation_job_for_identity,
    get_configured_simulation_ownership_store,
    get_simulation_job_for_identity,
    reset_configured_simulation_ownership_store_for_tests,
)

pytestmark = pytest.mark.mobile


def _identity(tenant_id: str, *, authenticated: bool = True) -> ProductRequestIdentity:
    return ProductRequestIdentity(
        tenant_id=tenant_id,
        principal=(f"token:{tenant_id}" if authenticated else f"local:{tenant_id}"),
        authenticated=authenticated,
        is_admin=False,
    )


def test_endpoint_adapter_creates_owned_job_and_hides_cross_tenant_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    reset_configured_simulation_ownership_store_for_tests()
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")

    created = create_simulation_job_for_identity(
        store,
        _identity("tenant-a"),
        "job-a",
        {"target_name": "ADRB2"},
    )

    assert created["job_id"] == "job-a"
    assert get_simulation_job_for_identity(
        store,
        _identity("tenant-a"),
        "job-a",
    )["job_id"] == "job-a"

    with pytest.raises(HTTPException) as cross_tenant:
        get_simulation_job_for_identity(
            store,
            _identity("tenant-b"),
            "job-a",
        )
    assert cross_tenant.value.status_code == 404


def test_legacy_unowned_job_is_available_only_in_explicit_local_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_configured_simulation_ownership_store_for_tests()
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("legacy-local", {"target_name": "legacy"})

    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    local_record = get_simulation_job_for_identity(
        store,
        _identity("local", authenticated=False),
        "legacy-local",
    )
    assert local_record["job_id"] == "legacy-local"

    monkeypatch.setattr(settings, "product_api_auth_required", True)
    with pytest.raises(HTTPException) as authenticated_boundary:
        get_simulation_job_for_identity(
            store,
            _identity("local", authenticated=True),
            "legacy-local",
        )
    assert authenticated_boundary.value.status_code == 404

    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", True)
    with pytest.raises(HTTPException) as hosted_boundary:
        get_simulation_job_for_identity(
            store,
            _identity("local", authenticated=False),
            "legacy-local",
        )
    assert hosted_boundary.value.status_code == 404


def test_endpoint_adapter_hides_invalid_job_identifier(tmp_path: Path) -> None:
    reset_configured_simulation_ownership_store_for_tests()
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")

    with pytest.raises(HTTPException) as exc_info:
        get_simulation_job_for_identity(
            store,
            _identity("tenant-a"),
            "../escape",
        )
    assert exc_info.value.status_code == 404


def test_ownership_store_cache_tracks_active_job_store_path(tmp_path: Path) -> None:
    reset_configured_simulation_ownership_store_for_tests()
    store_a = SQLiteJobStore(tmp_path / "a.sqlite3")
    store_b = SQLiteJobStore(tmp_path / "b.sqlite3")

    ownership_a = get_configured_simulation_ownership_store(store_a)
    ownership_a_again = get_configured_simulation_ownership_store(store_a)
    ownership_b = get_configured_simulation_ownership_store(store_b)

    assert ownership_a is ownership_a_again
    assert ownership_a.path == store_a.path
    assert ownership_b.path == store_b.path
    assert ownership_b is not ownership_a


def test_fastapi_injects_request_when_direct_call_compatibility_default_is_none() -> None:
    app = FastAPI()

    @app.get("/request-probe")
    def request_probe(request: Request = None) -> dict[str, object]:
        return {
            "request_injected": request is not None,
            "path": request.url.path if request is not None else "",
        }

    response = TestClient(app).get("/request-probe")

    assert response.status_code == 200
    assert response.json() == {
        "request_injected": True,
        "path": "/request-probe",
    }


def _function_calls(tree: ast.Module, function_name: str) -> set[str]:
    target: ast.AST | None = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            target = node
            break
    assert target is not None, f"missing function: {function_name}"

    calls: set[str] = set()
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    return calls


def test_live_simulation_routes_are_wired_to_identity_and_ownership_helpers() -> None:
    source = Path("api/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    submit_calls = _function_calls(tree, "submit_simulation")
    status_calls = _function_calls(tree, "get_simulation_status")
    result_calls = _function_calls(tree, "get_simulation_results")

    assert {"request_identity", "create_simulation_job_for_identity"} <= submit_calls
    assert {"request_identity", "get_simulation_job_for_identity"} <= status_calls
    assert {"request_identity", "get_simulation_job_for_identity"} <= result_calls
    assert "job_exists" not in status_calls
    assert "job_exists" not in result_calls

    assert source.index(
        "get_simulation_job_for_identity",
        source.index("def get_simulation_status"),
    ) < source.index(
        "job_status_path(job_id)",
        source.index("def get_simulation_status"),
    )
    assert source.index(
        "get_simulation_job_for_identity",
        source.index("def get_simulation_results"),
    ) < source.index(
        "job_status_path(job_id)",
        source.index("def get_simulation_results"),
    )
