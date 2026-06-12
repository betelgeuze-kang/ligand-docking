from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.request_privacy import sanitize_request_for_ledger


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _utc_now() -> str:
    return _format_utc(_utc_now_dt())


def _utc_after(seconds: int) -> str:
    return _format_utc(_utc_now_dt() + timedelta(seconds=seconds))


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
        with self._connect() as conn:
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
                    worker_id='',
                    lease_expires_at_utc='',
                    heartbeat_at_utc='',
                    attempt_count=0,
                    max_attempts=excluded.max_attempts,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (job_id, status, request_json, max_attempts, now, now),
            )
        return self.get_job(job_id) or {}

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        error: str = "",
        result_file: str = "",
        result_manifest_path: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        terminal_status = status in {"completed", "failed"}
        with self._connect() as conn:
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
            else:
                if terminal_status:
                    conn.execute(
                        """
                        UPDATE simulation_jobs
                        SET status=?, error=?, result_file=?, result_manifest_path=?,
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
                        SET status=?, error=?, result_file=?, result_manifest_path=?, updated_at_utc=?
                        WHERE job_id=?
                        """,
                        (status, error, result_file, result_manifest_path, now, job_id),
                    )
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
            row = conn.execute(
                """
                SELECT attempt_count, max_attempts
                FROM simulation_jobs
                WHERE job_id=? AND worker_id=? AND status='running'
                """,
                (job_id, worker_id),
            ).fetchone()
            if row is None:
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
