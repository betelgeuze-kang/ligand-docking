from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from api.job_store import SQLiteJobStore
from api.request_identity import ProductRequestIdentity
from api.simulation_job_ownership import (
    SQLiteSimulationJobOwnershipStore,
    create_owned_job,
    create_owned_job_if_absent,
    get_owned_job,
    validate_simulation_job_id,
)

pytestmark = pytest.mark.mobile


def _identity(tenant_id: str) -> ProductRequestIdentity:
    return ProductRequestIdentity(
        tenant_id=tenant_id,
        principal=f"token:{tenant_id}",
        authenticated=True,
        is_admin=False,
    )


def _admin() -> ProductRequestIdentity:
    return ProductRequestIdentity(
        tenant_id="admin",
        principal="admin-token",
        authenticated=True,
        is_admin=True,
    )


def _stores(tmp_path: Path) -> tuple[SQLiteJobStore, SQLiteSimulationJobOwnershipStore]:
    path = tmp_path / "simulation_jobs.sqlite3"
    return SQLiteJobStore(path), SQLiteSimulationJobOwnershipStore(path)


def test_owned_job_is_visible_only_to_owner_or_admin(tmp_path: Path) -> None:
    job_store, ownership_store = _stores(tmp_path)
    tenant_a = _identity("tenant-a")
    tenant_b = _identity("tenant-b")

    created = create_owned_job(
        job_store,
        ownership_store,
        tenant_a,
        "job-a",
        {"target_name": "ADRB2", "pdb_content": "PRIVATE"},
    )

    assert created["job_id"] == "job-a"
    assert ownership_store.owner_for_job("job-a") == "tenant-a"
    assert get_owned_job(job_store, ownership_store, tenant_a, "job-a")["job_id"] == "job-a"
    assert get_owned_job(job_store, ownership_store, _admin(), "job-a")["job_id"] == "job-a"

    with pytest.raises(HTTPException) as cross_tenant:
        get_owned_job(job_store, ownership_store, tenant_b, "job-a")
    assert cross_tenant.value.status_code == 404
    assert cross_tenant.value.detail == "job not found"


def test_non_admin_cannot_assign_a_different_owner(tmp_path: Path) -> None:
    job_store, ownership_store = _stores(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        create_owned_job(
            job_store,
            ownership_store,
            _identity("tenant-a"),
            "job-spoof",
            {"target_name": "ADRB2"},
            owner_tenant_id="tenant-b",
        )

    assert exc_info.value.status_code == 403
    assert job_store.get_job("job-spoof") is None
    assert ownership_store.owner_for_job("job-spoof") is None


def test_admin_can_create_for_an_explicit_tenant(tmp_path: Path) -> None:
    job_store, ownership_store = _stores(tmp_path)

    created = create_owned_job(
        job_store,
        ownership_store,
        _admin(),
        "job-admin-created",
        {"target_name": "ADRB2"},
        owner_tenant_id="tenant-b",
    )

    assert created["job_id"] == "job-admin-created"
    assert ownership_store.owner_for_job("job-admin-created") == "tenant-b"
    assert ownership_store.list_job_ids_for_tenant("tenant-b") == ["job-admin-created"]


def test_owner_binding_is_idempotent_but_immutable(tmp_path: Path) -> None:
    _, ownership_store = _stores(tmp_path)

    first = ownership_store.bind_owner("job-immutable", "tenant-a")
    second = ownership_store.bind_owner("job-immutable", "tenant-a")

    assert first["job_id"] == second["job_id"] == "job-immutable"
    assert first["tenant_id"] == second["tenant_id"] == "tenant-a"
    assert first["created_at_utc"] == second["created_at_utc"]

    with pytest.raises(PermissionError, match="immutable"):
        ownership_store.bind_owner("job-immutable", "tenant-b")
    assert ownership_store.owner_for_job("job-immutable") == "tenant-a"


def test_legacy_unowned_queue_row_cannot_be_claimed_or_read(tmp_path: Path) -> None:
    job_store, ownership_store = _stores(tmp_path)
    tenant_a = _identity("tenant-a")
    job_store.create_job("legacy-job", {"target_name": "legacy"})

    with pytest.raises(HTTPException) as read_exc:
        get_owned_job(job_store, ownership_store, tenant_a, "legacy-job")
    assert read_exc.value.status_code == 404

    with pytest.raises(HTTPException) as claim_exc:
        create_owned_job(
            job_store,
            ownership_store,
            tenant_a,
            "legacy-job",
            {"target_name": "replacement"},
        )
    assert claim_exc.value.status_code == 409
    assert claim_exc.value.detail == "existing job is missing an ownership binding"
    assert ownership_store.owner_for_job("legacy-job") is None


def test_create_if_absent_preserves_owner_and_existing_job(tmp_path: Path) -> None:
    job_store, ownership_store = _stores(tmp_path)
    tenant_a = _identity("tenant-a")

    first, first_created = create_owned_job_if_absent(
        job_store,
        ownership_store,
        tenant_a,
        "job-once",
        {"target_name": "first"},
    )
    second, second_created = create_owned_job_if_absent(
        job_store,
        ownership_store,
        tenant_a,
        "job-once",
        {"target_name": "second"},
    )

    assert first_created is True
    assert second_created is False
    assert first["request"]["target_name"] == "first"
    assert second["request"]["target_name"] == "first"
    assert ownership_store.owner_for_job("job-once") == "tenant-a"


def test_ownership_persists_across_store_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "simulation_jobs.sqlite3"
    job_store = SQLiteJobStore(db_path)
    ownership_store = SQLiteSimulationJobOwnershipStore(db_path)
    create_owned_job(
        job_store,
        ownership_store,
        _identity("tenant-a"),
        "job-persisted",
        {"target_name": "ADRB2"},
    )

    reopened = SQLiteSimulationJobOwnershipStore(db_path)
    assert reopened.owner_for_job("job-persisted") == "tenant-a"
    assert reopened.list_job_ids_for_tenant("tenant-a") == ["job-persisted"]


@pytest.mark.parametrize(
    "job_id",
    ["", "../job", "job/path", "job with spaces", "a" * 129],
)
def test_invalid_job_identifiers_are_rejected(job_id: str) -> None:
    with pytest.raises(ValueError):
        validate_simulation_job_id(job_id)
