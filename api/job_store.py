from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.config import settings
from api.request_privacy import sanitize_request_for_ledger


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _utc_now() -> str:
    return _format_utc(_utc_now_dt())


def _utc_after(seconds: int) -> str:
    return _format_utc(_utc_now_dt() + timedelta(seconds=seconds))


def _outbox_summary_from_request(job_id: str, status: str, request: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_request_for_ledger(request)
    summary: dict[str, Any] = {"job_id": job_id, "status": status}
    target_name = sanitized.get("target_name")
    if isinstance(target_name, str) and target_name:
        summary["target_name"] = target_name
    return summary


def _outbox_summary_for_status(job_id: str, status: str, *, error: str = "") -> dict[str, Any]:
    summary: dict[str, Any] = {"job_id": job_id, "status": status}
    if error:
        encoded = error.encode("utf-8")
        summary["error"] = {
            "redacted": True,
            "redaction": "sha256",
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "byte_length": len(encoded),
        }
    return summary


_configured_job_store: "SQLiteJobStore | None" = None
_configured_job_store_path: str | None = None


def _normalized_path(path_like: object) -> str:
    return str(Path(str(path_like)).expanduser())


def get_configured_job_store(path: str | Path | None = None) -> "SQLiteJobStore":
    """Return the configured SQLite store lazily, after runtime settings are patched."""
    global _configured_job_store, _configured_job_store_path

    configured_path = _normalized_path(path if path is not None else settings.api_job_store_path)
    if _configured_job_store is None or _configured_job_store_path != configured_path:
        _configured_job_store = SQLiteJobStore(configured_path)
        _configured_job_store_path = configured_path
    return _configured_job_store


def reset_configured_job_store_for_tests() -> None:
    global _configured_job_store, _configured_job_store_path

    _configured_job_store = None
    _configured_job_store_path = None


class SQLiteJobStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    result_file TEXT NOT NULL DEFAULT '',
                    result_manifest_path TEXT NOT NULL DEFAULT '',
                    evidence_bundle_path TEXT NOT NULL DEFAULT '',
                    evidence_bundle_sha256 TEXT NOT NULL DEFAULT '',
                    worker_id TEXT NOT NULL DEFAULT '',
                    lease_expires_at_utc TEXT NOT NULL DEFAULT '',
                    heartbeat_at_utc TEXT NOT NULL DEFAULT '',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(simulation_jobs)").fetchall()
            }
            if "result_manifest_path" not in columns:
                conn.execute(
                    "ALTER TABLE simulation_jobs ADD COLUMN result_manifest_path TEXT NOT NULL DEFAULT ''"
                )
            if "evidence_bundle_path" not in columns:
                conn.execute(
                    "ALTER TABLE simulation_jobs ADD COLUMN evidence_bundle_path TEXT NOT NULL DEFAULT ''"
                )
            if "evidence_bundle_sha256" not in columns:
                conn.execute(
                    "ALTER TABLE simulation_jobs ADD COLUMN evidence_bundle_sha256 TEXT NOT NULL DEFAULT ''"
                )
            if "worker_id" not in columns:
                conn.execute("ALTER TABLE simulation_jobs ADD COLUMN worker_id TEXT NOT NULL DEFAULT ''")
            if "lease_expires_at_utc" not in columns:
                conn.execute(
                    "ALTER TABLE simulation_jobs ADD COLUMN lease_expires_at_utc TEXT NOT NULL DEFAULT ''"
                )
            if "heartbeat_at_utc" not in columns:
                conn.execute("ALTER TABLE simulation_jobs ADD COLUMN heartbeat_at_utc TEXT NOT NULL DEFAULT ''")
            if "attempt_count" not in columns:
                conn.execute("ALTER TABLE simulation_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
            if "max_attempts" not in columns:
                conn.execute("ALTER TABLE simulation_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_simulation_jobs_status ON simulation_jobs(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_simulation_jobs_lease ON simulation_jobs(status, lease_expires_at_utc)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_job_outbox (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    delivery_state TEXT NOT NULL DEFAULT 'pending',
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_simulation_job_outbox_pending
                ON simulation_job_outbox(delivery_state, created_at_utc)
                """
            )

    def _insert_outbox_event(
        self,
        conn: sqlite3.Connection,
        *,
        job_id: str,
        event_type: str,
        payload: dict[str, Any],
        now: str,
    ) -> int:
        cursor = conn.execute(
            """
            INSERT INTO simulation_job_outbox(
                job_id, event_type, payload_json, delivery_state, created_at_utc, updated_at_utc
            )
            VALUES(?, ?, ?, 'pending', ?, ?)
            """,
            (
                job_id,
                event_type,
                json.dumps(payload, sort_keys=True, ensure_ascii=False),
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)

    def list_pending_outbox_events(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_id, job_id, event_type, payload_json, delivery_state,
                       created_at_utc, updated_at_utc
                FROM simulation_job_outbox
                WHERE delivery_state='pending'
                ORDER BY event_id ASC
                """
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            try:
                event["payload"] = json.loads(event.pop("payload_json"))
            except json.JSONDecodeError:
                event["payload"] = {}
            events.append(event)
        return events

    def mark_outbox_event_delivered(self, event_id: int) -> bool:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT delivery_state FROM simulation_job_outbox WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            if row["delivery_state"] == "delivered":
                conn.commit()
                return True
            if row["delivery_state"] != "pending":
                conn.rollback()
                return False
            conn.execute(
                """
                UPDATE simulation_job_outbox
                SET delivery_state='delivered', updated_at_utc=?
                WHERE event_id=?
                """,
                (now, event_id),
            )
            conn.commit()
        return True

    def mark_outbox_event_recovered(self, event_id: int) -> bool:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT delivery_state FROM simulation_job_outbox WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            if row["delivery_state"] == "recovered":
                conn.commit()
                return True
            if row["delivery_state"] != "pending":
                conn.rollback()
                return False
            conn.execute(
                """
                UPDATE simulation_job_outbox
                SET delivery_state='recovered', updated_at_utc=?
                WHERE event_id=?
                """,
                (now, event_id),
            )
            conn.commit()
        return True

    def create_job(
        self,
        job_id: str,
        request: dict[str, Any],
        *,
        status: str = "submitted",
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        now = _utc_now()
        request_json = json.dumps(sanitize_request_for_ledger(request), sort_keys=True, ensure_ascii=False)
        outbox_payload = _outbox_summary_from_request(job_id, status, request)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO simulation_jobs(
                    job_id, status, request_json, max_attempts, created_at_utc, updated_at_utc
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    request_json=excluded.request_json,
                    error='',
                    result_file='',
                    result_manifest_path='',
                    evidence_bundle_path='',
                    evidence_bundle_sha256='',
                    worker_id='',
                    lease_expires_at_utc='',
                    heartbeat_at_utc='',
                    attempt_count=0,
                    max_attempts=excluded.max_attempts,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (job_id, status, request_json, max_attempts, now, now),
            )
            self._insert_outbox_event(
                conn,
                job_id=job_id,
                event_type="job_created",
                payload=outbox_payload,
                now=now,
            )
            conn.commit()
        return self.get_job(job_id) or {}

    def create_job_if_absent(
        self,
        job_id: str,
        request: dict[str, Any],
        *,
        status: str = "submitted",
        max_attempts: int = 3,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically insert a queue row without resetting an existing job.

        Returns ``(record, created)``. The existing row is preserved exactly
        when another dispatcher has already inserted the same ``job_id``.
        """

        now = _utc_now()
        request_json = json.dumps(
            sanitize_request_for_ledger(request),
            sort_keys=True,
            ensure_ascii=False,
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO simulation_jobs(
                    job_id, status, request_json, max_attempts, created_at_utc, updated_at_utc
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (job_id, status, request_json, max_attempts, now, now),
            )
            created = cursor.rowcount == 1
            if created:
                # Emit the durable creation event in the same transaction so a
                # crash/reopen can recover dispatcher-created jobs, matching the
                # behavior of create_job(). When the row already exists we leave
                # the existing job (and its prior outbox events) untouched.
                self._insert_outbox_event(
                    conn,
                    job_id=job_id,
                    event_type="job_created",
                    payload=_outbox_summary_from_request(job_id, status, request),
                    now=now,
                )
            conn.commit()
        return self.get_job(job_id) or {}, created

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        error: str = "",
        result_file: str = "",
        result_manifest_path: str | None = None,
        evidence_bundle_path: str | None = None,
        evidence_bundle_sha256: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        terminal_status = status in {"completed", "failed"}
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing_row = conn.execute(
                "SELECT status FROM simulation_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            previous_status = str(existing_row["status"]) if existing_row is not None else ""
            if result_manifest_path is None:
                if terminal_status:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?,
                            worker_id='', lease_expires_at_utc='', heartbeat_at_utc='',
                            updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (status, error, result_file, now, job_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?, updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (status, error, result_file, now, job_id),
                    )
            elif evidence_bundle_path is not None and evidence_bundle_sha256 is not None:
                if terminal_status:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?, result_manifest_path=?,
                            evidence_bundle_path=?, evidence_bundle_sha256=?,
                            worker_id='', lease_expires_at_utc='', heartbeat_at_utc='',
                            updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (
                            status,
                            error,
                            result_file,
                            result_manifest_path,
                            evidence_bundle_path,
                            evidence_bundle_sha256,
                            now,
                            job_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?, result_manifest_path=?,
                            evidence_bundle_path=?, evidence_bundle_sha256=?, updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (
                            status,
                            error,
                            result_file,
                            result_manifest_path,
                            evidence_bundle_path,
                            evidence_bundle_sha256,
                            now,
                            job_id,
                        ),
                    )
            else:
                if terminal_status:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?, result_manifest_path=?,
                            evidence_bundle_path='', evidence_bundle_sha256='',
                            worker_id='', lease_expires_at_utc='', heartbeat_at_utc='',
                            updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (status, error, result_file, result_manifest_path, now, job_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?, result_manifest_path=?,
                            evidence_bundle_path='', evidence_bundle_sha256='', updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (status, error, result_file, result_manifest_path, now, job_id),
                    )
            if terminal_status and existing_row is not None and previous_status != status:
                self._insert_outbox_event(
                    conn,
                    job_id=job_id,
                    event_type="job_status_changed",
                    payload=_outbox_summary_for_status(job_id, status, error=error),
                    now=now,
                )
            conn.commit()
        return self.get_job(job_id) or {}

    def acquire_next_job(self, worker_id: str, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        now = _utc_now()
        lease_until = _utc_after(lease_seconds)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT job_id
                FROM simulation_jobs
                WHERE attempt_count < max_attempts
                  AND (
                    status IN ('submitted', 'retry_ready')
                    OR (
                      status='running'
                      AND lease_expires_at_utc != ''
                      AND lease_expires_at_utc <= ?
                    )
                  )
                ORDER BY created_at_utc ASC, job_id ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            job_id = str(row["job_id"])
            conn.execute(
                """
                UPDATE simulation_jobs
                SET status='running',
                    worker_id=?,
                    lease_expires_at_utc=?,
                    heartbeat_at_utc=?,
                    attempt_count=attempt_count + 1,
                    updated_at_utc=?
                WHERE job_id=?
                """,
                (worker_id, lease_until, now, now, job_id),
            )
            conn.commit()
        return self.get_job(job_id)

    def heartbeat_job(self, job_id: str, worker_id: str, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        now = _utc_now()
        lease_until = _utc_after(lease_seconds)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE simulation_jobs
                SET lease_expires_at_utc=?, heartbeat_at_utc=?, updated_at_utc=?
                WHERE job_id=? AND worker_id=? AND status='running'
                """,
                (lease_until, now, now, job_id, worker_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_job(job_id)

    def release_job_for_retry(self, job_id: str, worker_id: str, *, error: str = "") -> dict[str, Any] | None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT attempt_count, max_attempts
                FROM simulation_jobs
                WHERE job_id=? AND worker_id=? AND status='running'
                """,
                (job_id, worker_id),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            next_status = "retry_ready" if int(row["attempt_count"]) < int(row["max_attempts"]) else "failed"
            conn.execute(
                """
                UPDATE simulation_jobs
                SET status=?, error=?,
                    worker_id='', lease_expires_at_utc='', heartbeat_at_utc='',
                    updated_at_utc=?
                WHERE job_id=?
                """,
                (next_status, error, now, job_id),
            )
            self._insert_outbox_event(
                conn,
                job_id=job_id,
                event_type="job_status_changed",
                payload=_outbox_summary_for_status(job_id, next_status, error=error),
                now=now,
            )
            conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM simulation_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        try:
            record["request"] = json.loads(record.pop("request_json"))
        except json.JSONDecodeError:
            record["request"] = {}
        return record

    def job_exists(self, job_id: str) -> bool:
        return self.get_job(job_id) is not None
