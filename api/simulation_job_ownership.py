from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Any

from fastapi import HTTPException

from api.job_store import SQLiteJobStore
from api.request_identity import (
    ProductRequestIdentity,
    normalize_tenant_id,
    require_tenant_match,
)

_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def validate_simulation_job_id(value: Any) -> str:
    """Return a path/SQL-safe job identifier or reject it."""

    job_id = str(value or "").strip()
    if not _JOB_ID_RE.fullmatch(job_id):
        raise ValueError("job_id must be a simple 1-128 character identifier")
    return job_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SQLiteSimulationJobOwnershipStore:
    """Tenant ownership ledger colocated with the SQLite simulation queue.

    Ownership is stored in a separate table so the security slice can be
    reviewed independently from queue/lease behavior. A simulation row without
    a matching ownership row is deliberately inaccessible.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_job_ownership (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_simulation_job_ownership_tenant
                ON simulation_job_ownership(tenant_id, job_id)
                """
            )

    def bind_owner(self, job_id: Any, tenant_id: Any) -> dict[str, str]:
        """Create an idempotent owner binding and reject all re-binding."""

        normalized_job_id = validate_simulation_job_id(job_id)
        normalized_tenant_id = normalize_tenant_id(tenant_id)
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT tenant_id, created_at_utc
                FROM simulation_job_ownership
                WHERE job_id=?
                """,
                (normalized_job_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO simulation_job_ownership(
                        job_id, tenant_id, created_at_utc, updated_at_utc
                    ) VALUES(?, ?, ?, ?)
                    """,
                    (normalized_job_id, normalized_tenant_id, now, now),
                )
                created_at = now
            else:
                existing_tenant = str(row["tenant_id"])
                if existing_tenant != normalized_tenant_id:
                    raise PermissionError("simulation job owner binding is immutable")
                conn.execute(
                    """
                    UPDATE simulation_job_ownership
                    SET updated_at_utc=?
                    WHERE job_id=?
                    """,
                    (now, normalized_job_id),
                )
                created_at = str(row["created_at_utc"])
        return {
            "job_id": normalized_job_id,
            "tenant_id": normalized_tenant_id,
            "created_at_utc": created_at,
            "updated_at_utc": now,
        }

    def owner_for_job(self, job_id: Any) -> str | None:
        normalized_job_id = validate_simulation_job_id(job_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id
                FROM simulation_job_ownership
                WHERE job_id=?
                """,
                (normalized_job_id,),
            ).fetchone()
        return str(row["tenant_id"]) if row is not None else None

    def list_job_ids_for_tenant(self, tenant_id: Any) -> list[str]:
        normalized_tenant_id = normalize_tenant_id(tenant_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id
                FROM simulation_job_ownership
                WHERE tenant_id=?
                ORDER BY job_id ASC
                """,
                (normalized_tenant_id,),
            ).fetchall()
        return [str(row["job_id"]) for row in rows]

    def require_access(
        self,
        identity: ProductRequestIdentity,
        job_id: Any,
        *,
        resource: str = "job",
    ) -> str:
        normalized_job_id = validate_simulation_job_id(job_id)
        owner = self.owner_for_job(normalized_job_id)
        if owner is None:
            raise HTTPException(status_code=404, detail=f"{resource} not found")
        require_tenant_match(identity, owner, resource=resource)
        return owner


def _requested_owner(
    identity: ProductRequestIdentity,
    owner_tenant_id: Any | None,
) -> str:
    owner = normalize_tenant_id(owner_tenant_id or identity.tenant_id)
    if not identity.is_admin and owner != identity.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="job owner must match authenticated tenant",
        )
    return owner


def _guard_existing_job_binding(
    job_store: SQLiteJobStore,
    ownership_store: SQLiteSimulationJobOwnershipStore,
    identity: ProductRequestIdentity,
    job_id: str,
    owner: str,
) -> None:
    existing = job_store.get_job(job_id)
    if existing is None:
        return
    existing_owner = ownership_store.owner_for_job(job_id)
    if existing_owner is None:
        # A legacy or partially written queue row must not be claimable by the
        # first caller that happens to know its identifier.
        raise HTTPException(
            status_code=409,
            detail="existing job is missing an ownership binding",
        )
    require_tenant_match(identity, existing_owner, resource="job")
    if existing_owner != owner:
        raise HTTPException(status_code=409, detail="job owner binding conflict")


def create_owned_job(
    job_store: SQLiteJobStore,
    ownership_store: SQLiteSimulationJobOwnershipStore,
    identity: ProductRequestIdentity,
    job_id: Any,
    request: dict[str, Any],
    *,
    status: str = "submitted",
    max_attempts: int = 3,
    owner_tenant_id: Any | None = None,
) -> dict[str, Any]:
    """Create/update a simulation row only after immutable ownership is bound."""

    normalized_job_id = validate_simulation_job_id(job_id)
    owner = _requested_owner(identity, owner_tenant_id)
    _guard_existing_job_binding(
        job_store,
        ownership_store,
        identity,
        normalized_job_id,
        owner,
    )
    ownership_store.bind_owner(normalized_job_id, owner)
    return job_store.create_job(
        normalized_job_id,
        request,
        status=status,
        max_attempts=max_attempts,
    )


def create_owned_job_if_absent(
    job_store: SQLiteJobStore,
    ownership_store: SQLiteSimulationJobOwnershipStore,
    identity: ProductRequestIdentity,
    job_id: Any,
    request: dict[str, Any],
    *,
    status: str = "submitted",
    max_attempts: int = 3,
    owner_tenant_id: Any | None = None,
) -> tuple[dict[str, Any], bool]:
    normalized_job_id = validate_simulation_job_id(job_id)
    owner = _requested_owner(identity, owner_tenant_id)
    _guard_existing_job_binding(
        job_store,
        ownership_store,
        identity,
        normalized_job_id,
        owner,
    )
    ownership_store.bind_owner(normalized_job_id, owner)
    return job_store.create_job_if_absent(
        normalized_job_id,
        request,
        status=status,
        max_attempts=max_attempts,
    )


def get_owned_job(
    job_store: SQLiteJobStore,
    ownership_store: SQLiteSimulationJobOwnershipStore,
    identity: ProductRequestIdentity,
    job_id: Any,
    *,
    resource: str = "job",
) -> dict[str, Any]:
    normalized_job_id = validate_simulation_job_id(job_id)
    record = job_store.get_job(normalized_job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"{resource} not found")
    ownership_store.require_access(identity, normalized_job_id, resource=resource)
    return record
