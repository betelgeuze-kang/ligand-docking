from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config import settings
from api.product_docking import router
from api.security import ProductSecurityMiddleware

pytestmark = pytest.mark.mobile


def _configure_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(settings, "product_api_auth_required", True)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_token", "tenant-a-token")
    monkeypatch.setattr(settings, "product_api_token_tenant_id", "tenant-a")
    monkeypatch.setattr(settings, "product_api_admin_token", "admin-token")
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 10_000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 1_000_000)


def _record(job_id: str, customer_id: str) -> dict[str, object]:
    return {
        "job_id": job_id,
        "root_job_id": job_id,
        "request_sha256": f"sha-{job_id}",
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "target_id": "ADRB2",
        "customer_id": customer_id,
        "user_id": f"user-{customer_id}",
        "status": "accepted_fail_closed",
        "validation_status": "pass",
        "blockers": [],
        "warnings": [],
        "event_history": [],
        "progress_percent": 0.0,
        "progress_state": "ledger_intake_recorded",
        "current_step": "contract_validation",
        "queue_status": "queued_fail_closed",
        "queue_position": 0,
        "worker_state": "not_started_fail_closed",
        "cancellable": True,
        "retryable": True,
        "attempt_index": 1,
        "max_retry_attempts": 3,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": "tenant-isolation-test-only",
    }


def _write_record(tmp_path: Path, job_id: str, customer_id: str) -> Path:
    jobs_dir = tmp_path / "results" / "product_docking_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    path = jobs_dir / f"{job_id}.json"
    path.write_text(
        json.dumps(_record(job_id, customer_id), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)
    app.include_router(router)
    return app


def _tenant_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer tenant-a-token",
        "X-Tenant-ID": "tenant-a",
    }


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer admin-token"}


def test_product_job_read_list_history_and_mutation_are_tenant_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_auth(monkeypatch, tmp_path)
    own_path = _write_record(tmp_path, "job-a", "tenant-a")
    _write_record(tmp_path, "job-b", "tenant-b")
    client = TestClient(_app())

    own = client.get("/product/docking/jobs/job-a", headers=_tenant_headers())
    cross = client.get("/product/docking/jobs/job-b", headers=_tenant_headers())
    listing = client.get("/product/docking/jobs", headers=_tenant_headers())
    own_history = client.get(
        "/product/docking/jobs/job-a/history",
        headers=_tenant_headers(),
    )
    cross_history = client.get(
        "/product/docking/jobs/job-b/history",
        headers=_tenant_headers(),
    )
    cross_cancel = client.post(
        "/product/docking/jobs/job-b/cancel",
        headers=_tenant_headers(),
        json={"reason": "must-not-apply", "actor": "forged-actor"},
    )
    cross_retry = client.post(
        "/product/docking/jobs/job-b/retry",
        headers=_tenant_headers(),
        json={"reason": "must-not-apply", "actor": "forged-actor"},
    )
    own_cancel = client.post(
        "/product/docking/jobs/job-a/cancel",
        headers=_tenant_headers(),
        json={"reason": "operator request", "actor": "forged-actor"},
    )

    assert own.status_code == 200
    assert own.json()["job_id"] == "job-a"
    assert own.json()["customer_id"] == "tenant-a"
    assert cross.status_code == 404
    assert cross_history.status_code == 404
    assert cross_cancel.status_code == 404
    assert cross_retry.status_code == 404
    assert listing.status_code == 200
    assert [row["job_id"] for row in listing.json()["jobs"]] == ["job-a"]
    assert listing.json()["customer_id_filter"] == "tenant-a"
    assert own_history.status_code == 200
    assert own_cancel.status_code == 200

    updated = json.loads(own_path.read_text(encoding="utf-8"))
    assert updated["last_event_type"] == "cancel_requested"
    assert updated["event_history"][-1]["actor"] == "token:tenant-a"
    assert updated["event_history"][-1]["actor"] != "forged-actor"


def test_debug_diagnostics_require_admin_and_admin_can_review_cross_tenant_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_auth(monkeypatch, tmp_path)
    _write_record(tmp_path, "job-a", "tenant-a")
    _write_record(tmp_path, "job-b", "tenant-b")
    client = TestClient(_app())

    tenant_debug = client.get(
        "/product/docking/jobs/job-a?debug=true",
        headers=_tenant_headers(),
    )
    admin_cross = client.get(
        "/product/docking/jobs/job-b?debug=true",
        headers=_admin_headers(),
    )
    admin_listing = client.get(
        "/product/docking/jobs",
        headers=_admin_headers(),
    )

    assert tenant_debug.status_code == 403
    assert admin_cross.status_code == 200
    assert "diagnostics" in admin_cross.json()
    assert admin_listing.status_code == 200
    assert {row["job_id"] for row in admin_listing.json()["jobs"]} == {"job-a", "job-b"}


def test_submission_rejects_cross_tenant_customer_before_scientific_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_auth(monkeypatch, tmp_path)
    client = TestClient(_app())

    response = client.post(
        "/product/docking/jobs",
        headers=_tenant_headers(),
        json={
            "family": "gpcr",
            "customer_id": "tenant-b",
            "target_id": "ADRB2",
            "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "customer_id must match authenticated tenant"
    assert not (tmp_path / "results" / "product_docking_jobs").exists()


def test_invalid_job_identifier_is_hidden_as_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_auth(monkeypatch, tmp_path)
    _write_record(tmp_path, "job-a", "tenant-a")
    client = TestClient(_app())

    response = client.get(
        "/product/docking/jobs/%2E%2E",
        headers=_tenant_headers(),
    )

    assert response.status_code == 404
