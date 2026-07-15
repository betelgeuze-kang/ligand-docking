"""Atomic simulation admission across ownership, queue, and outbox tables."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from fastapi import HTTPException

from api.job_store import SQLiteJobStore, materialize_execution_request
from api.request_identity import ProductRequestIdentity, normalize_tenant_id
from api.simulation_job_ownership import validate_simulation_job_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_owned_job_atomic(
    job_store: SQLiteJobStore,
    identity: ProductRequestIdentity,
    job_id: Any,
    request: dict[str, Any],
    *,
    status: str = "submitted",
    max_attempts: int = 3,
    owner_tenant_id: str | None = None,
) -> dict[str, Any]:
    """Create owner, queue row, request fingerprint, and outbox event atomically."""

    normalized_job_id = validate_simulation_job_id(job_id)
    owner = normalize_tenant_id(owner_tenant_id or identity.tenant_id)
    if not identity.is_admin and owner != identity.tenant_id:
        raise HTTPException(status_code=403, detail="job owner must match authenticated tenant")
    if not isinstance(request, dict):
        raise TypeError("request must be a dictionary")
    if int(max_attempts) < 1:
        raise ValueError("max_attempts must be positive")

    now = _utc_now()
    (
        sanitized,
        request_sha256,
        execution_request_sha256,
        execution_request_transform_id,
    ) = materialize_execution_request(request)
    request_json = json.dumps(
        sanitized,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    outbox_payload: dict[str, Any] = {
        "job_id": normalized_job_id,
        "status": str(status),
    }
    target_name = sanitized.get("target_name")
    if isinstance(target_name, str) and target_name:
        outbox_payload["target_name"] = target_name

    conn = job_store._connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing_job = conn.execute(
            "SELECT job_id FROM simulation_jobs WHERE job_id=?",
            (normalized_job_id,),
        ).fetchone()
        existing_owner = conn.execute(
            "SELECT tenant_id FROM simulation_job_ownership WHERE job_id=?",
            (normalized_job_id,),
        ).fetchone()
        if existing_job is not None:
            if existing_owner is None:
                raise HTTPException(
                    status_code=409,
                    detail="existing job is missing an ownership binding",
                )
            if str(existing_owner["tenant_id"]) != owner:
                raise HTTPException(status_code=404, detail="job not found")
            raise HTTPException(status_code=409, detail="job already exists")
        if existing_owner is not None:
            raise HTTPException(status_code=409, detail="orphan ownership binding exists")

        conn.execute(
            """
            INSERT INTO simulation_jobs(
                job_id, status, request_json, request_sha256,
                execution_request_sha256, execution_request_transform_id,
                max_attempts, created_at_utc, updated_at_utc
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_job_id,
                str(status),
                request_json,
                request_sha256,
                execution_request_sha256,
                execution_request_transform_id,
                int(max_attempts),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO simulation_job_ownership(
                job_id, tenant_id, created_at_utc, updated_at_utc
            ) VALUES(?, ?, ?, ?)
            """,
            (normalized_job_id, owner, now, now),
        )
        conn.execute(
            """
            INSERT INTO simulation_job_outbox(
                job_id, event_type, payload_json, delivery_state,
                created_at_utc, updated_at_utc
            ) VALUES(?, 'job_created', ?, 'pending', ?, ?)
            """,
            (
                normalized_job_id,
                json.dumps(outbox_payload, sort_keys=True, ensure_ascii=False),
                now,
                now,
            ),
        )
        committed_row = conn.execute(
            "SELECT * FROM simulation_jobs WHERE job_id=?",
            (normalized_job_id,),
        ).fetchone()
        if committed_row is None:
            raise RuntimeError("atomic job admission has no readable queue row")
        record = dict(committed_row)
        try:
            materialized_request = json.loads(str(record.pop("request_json")))
        except json.JSONDecodeError as exc:
            raise RuntimeError("atomic job admission request JSON is unreadable") from exc
        if not isinstance(materialized_request, dict):
            raise RuntimeError("atomic job admission request JSON is not an object")
        record["request"] = materialized_request
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return record


__all__ = ["create_owned_job_atomic"]
