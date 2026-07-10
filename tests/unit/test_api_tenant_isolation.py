from __future__ import annotations

from pathlib import Path

import pytest


def _docking_request(tenant_id: str) -> dict[str, object]:
    return {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "customer_id": tenant_id,
        "user_id": f"user-{tenant_id}",
        "target_id": "ADRB2",
        "pdb_content": (
            "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"
        ),
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
    }


def _configure_security(settings: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 10_000)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", 10_000)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 10_000_000)
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(tmp_path / "audit.jsonl"))


def test_product_docking_objects_are_tenant_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.config import settings
    from api.product_docking import router
    from api.security import ProductSecurityMiddleware
    from betelgeuze_product.docking_request import (
        build_docking_job_record,
        persist_docking_job_record,
    )

    _configure_security(settings, monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    jobs_dir = tmp_path / "results" / "product_docking_jobs"
    for job_id, tenant_id in (("job-a", "tenant-a"), ("job-b", "tenant-b")):
        record = build_docking_job_record(
            _docking_request(tenant_id),
            job_id=job_id,
            source_host="unit-test",
        )
        persist_docking_job_record(record, jobs_dir)

    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)
    app.include_router(router)
    client = TestClient(app)

    own = client.get("/product/docking/jobs/job-a", headers={"X-Tenant-ID": "tenant-a"})
    cross = client.get("/product/docking/jobs/job-b", headers={"X-Tenant-ID": "tenant-a"})
    listing = client.get("/product/docking/jobs", headers={"X-Tenant-ID": "tenant-a"})
    cross_cancel = client.post(
        "/product/docking/jobs/job-b/cancel",
        headers={"X-Tenant-ID": "tenant-a"},
        json={"reason": "should-not-apply"},
    )
    debug = client.get(
        "/product/docking/jobs/job-a?debug=true",
        headers={"X-Tenant-ID": "tenant-a"},
    )

    assert own.status_code == 200
    assert cross.status_code == 404
    assert cross_cancel.status_code == 404
    assert debug.status_code == 403
    assert listing.status_code == 200
    assert [row["job_id"] for row in listing.json()["jobs"]] == ["job-a"]


def test_simulation_status_is_tenant_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import api.main as main
    from api.config import settings
    from api.worker import write_status_file

    _configure_security(settings, monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    main.job_store = None
    main._job_store_path = None
    store = main.get_job_store()
    store.create_job("sim-a", {"runner_profile_id": "unit"}, tenant_id="tenant-a")
    store.create_job("sim-b", {"runner_profile_id": "unit"}, tenant_id="tenant-b")
    status_path = tmp_path / "results" / "sim-a" / "status.json"
    write_status_file(str(status_path), {"job_id": "sim-a", "status": "submitted"})

    client = TestClient(main.app)
    own = client.get("/status/sim-a", headers={"X-Tenant-ID": "tenant-a"})
    cross = client.get("/status/sim-a", headers={"X-Tenant-ID": "tenant-b"})

    assert own.status_code == 200
    assert own.json()["job_id"] == "sim-a"
    assert cross.status_code == 404
