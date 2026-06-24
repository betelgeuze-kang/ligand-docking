from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from api.job_store import SQLiteJobStore
from api.request_privacy import sanitize_request_for_ledger

OUTBOX_EVENT_TYPE = "docking_dispatch_enqueued"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _connect(store: SQLiteJobStore) -> sqlite3.Connection:
    conn = sqlite3.connect(str(store.path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_outbox_schema(store: SQLiteJobStore) -> None:
    with _connect(store) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docking_dispatch_outbox (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                delivered_at_utc TEXT NOT NULL DEFAULT '',
                UNIQUE(job_id, event_type)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_docking_dispatch_outbox_status
            ON docking_dispatch_outbox(status, created_at_utc)
            """
        )


def enqueue_job_with_outbox(
    store: SQLiteJobStore,
    *,
    job_id: str,
    request: dict[str, Any],
    event_payload: dict[str, Any],
    status: str = "submitted",
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Atomically insert the simulation job and its local dispatch outbox event."""

    ensure_outbox_schema(store)
    now = _utc_now()
    sanitized_request = sanitize_request_for_ledger(request)
    request_json = _canonical_json(sanitized_request)
    sanitized_event = sanitize_request_for_ledger(event_payload)
    event_json = _canonical_json(sanitized_event)
    event_id = f"{OUTBOX_EVENT_TYPE}:{job_id}"

    with _connect(store) as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT request_json, status FROM simulation_jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        job_created = False
        if existing is None:
            conn.execute(
                """
                INSERT INTO simulation_jobs(
                    job_id, status, request_json, max_attempts, created_at_utc, updated_at_utc
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (job_id, status, request_json, int(max_attempts), now, now),
            )
            job_created = True
            sqlite_status = status
        else:
            observed_request = _canonical_json(json.loads(str(existing["request_json"])))
            if observed_request != request_json:
                conn.rollback()
                raise ValueError(f"docking dispatch idempotency conflict for job_id={job_id}")
            sqlite_status = str(existing["status"])

        existing_outbox = conn.execute(
            "SELECT event_id, status FROM docking_dispatch_outbox WHERE job_id=? AND event_type=?",
            (job_id, OUTBOX_EVENT_TYPE),
        ).fetchone()
        outbox_created = False
        if existing_outbox is None:
            conn.execute(
                """
                INSERT INTO docking_dispatch_outbox(
                    event_id, job_id, event_type, payload_json, status,
                    created_at_utc, updated_at_utc
                ) VALUES(?, ?, ?, ?, 'pending', ?, ?)
                """,
                (event_id, job_id, OUTBOX_EVENT_TYPE, event_json, now, now),
            )
            outbox_created = True
            outbox_status = "pending"
        else:
            event_id = str(existing_outbox["event_id"])
            outbox_status = str(existing_outbox["status"])
        conn.commit()

    return {
        "job_id": job_id,
        "event_id": event_id,
        "job_created": job_created,
        "outbox_created": outbox_created,
        "sqlite_status": sqlite_status,
        "outbox_status": outbox_status,
        "already_present": not job_created,
    }


def pending_outbox_events(store: SQLiteJobStore, *, limit: int = 100) -> list[dict[str, Any]]:
    ensure_outbox_schema(store)
    with _connect(store) as conn:
        rows = conn.execute(
            """
            SELECT * FROM docking_dispatch_outbox
            WHERE status IN ('pending', 'retry_ready')
            ORDER BY created_at_utc ASC, event_id ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        try:
            record["payload"] = json.loads(str(record.pop("payload_json")))
        except json.JSONDecodeError:
            record["payload"] = {}
        events.append(record)
    return events


def mark_outbox_delivered(store: SQLiteJobStore, event_id: str) -> None:
    ensure_outbox_schema(store)
    now = _utc_now()
    with _connect(store) as conn:
        conn.execute(
            """
            UPDATE docking_dispatch_outbox
            SET status='delivered', delivered_at_utc=?, updated_at_utc=?, last_error=''
            WHERE event_id=?
            """,
            (now, now, event_id),
        )


def mark_outbox_failed(store: SQLiteJobStore, event_id: str, error: str) -> None:
    ensure_outbox_schema(store)
    now = _utc_now()
    with _connect(store) as conn:
        conn.execute(
            """
            UPDATE docking_dispatch_outbox
            SET status='retry_ready', attempt_count=attempt_count + 1,
                last_error=?, updated_at_utc=?
            WHERE event_id=?
            """,
            (str(error or "")[:2000], now, event_id),
        )


def get_outbox_event(store: SQLiteJobStore, event_id: str) -> dict[str, Any] | None:
    ensure_outbox_schema(store)
    with _connect(store) as conn:
        row = conn.execute(
            "SELECT * FROM docking_dispatch_outbox WHERE event_id=?",
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    record = dict(row)
    try:
        record["payload"] = json.loads(str(record.pop("payload_json")))
    except json.JSONDecodeError:
        record["payload"] = {}
    return record
