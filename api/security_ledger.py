"""Process-shared rate-limit and tenant-quota accounting for the product API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time

from api.sqlite_runtime import connect_sqlite


class SecurityLedgerError(RuntimeError):
    """Persistent security accounting could not be completed safely."""


class SQLiteSecurityLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.path)

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS api_rate_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rate_key TEXT NOT NULL,
                        observed_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_api_rate_events_key_time
                    ON api_rate_events(rate_key, observed_at)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS api_daily_quota (
                        tenant_id TEXT NOT NULL,
                        day_utc TEXT NOT NULL,
                        request_count INTEGER NOT NULL,
                        updated_at REAL NOT NULL,
                        PRIMARY KEY(tenant_id, day_utc)
                    )
                    """
                )
        except (OSError, sqlite3.Error) as exc:
            raise SecurityLedgerError("persistent security ledger initialization failed") from exc

    def consume(
        self,
        *,
        rate_key: str,
        tenant_id: str,
        rate_limit_per_minute: int,
        tenant_daily_quota: int,
        now: float | None = None,
    ) -> str | None:
        """Atomically account one admitted request or return its block code."""

        observed_at = float(time.time() if now is None else now)
        if not rate_key or not tenant_id:
            raise SecurityLedgerError("rate_key and tenant_id must be non-empty")
        rate_limit = int(rate_limit_per_minute)
        quota = int(tenant_daily_quota)
        day = datetime.fromtimestamp(observed_at, tz=timezone.utc).strftime("%Y-%m-%d")
        cutoff = observed_at - 60.0
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM api_rate_events WHERE observed_at < ?", (cutoff,))
                if rate_limit > 0:
                    count = int(
                        conn.execute(
                            """
                            SELECT COUNT(*) AS count
                            FROM api_rate_events
                            WHERE rate_key=? AND observed_at>=?
                            """,
                            (rate_key, cutoff),
                        ).fetchone()["count"]
                    )
                    if count >= rate_limit:
                        conn.rollback()
                        return "rate_limited"
                if quota > 0:
                    row = conn.execute(
                        """
                        SELECT request_count FROM api_daily_quota
                        WHERE tenant_id=? AND day_utc=?
                        """,
                        (tenant_id, day),
                    ).fetchone()
                    current = 0 if row is None else int(row["request_count"])
                    if current >= quota:
                        conn.rollback()
                        return "tenant_quota_exceeded"
                conn.execute(
                    "INSERT INTO api_rate_events(rate_key, observed_at) VALUES(?, ?)",
                    (rate_key, observed_at),
                )
                conn.execute(
                    """
                    INSERT INTO api_daily_quota(tenant_id, day_utc, request_count, updated_at)
                    VALUES(?, ?, 1, ?)
                    ON CONFLICT(tenant_id, day_utc) DO UPDATE SET
                        request_count=api_daily_quota.request_count + 1,
                        updated_at=excluded.updated_at
                    """,
                    (tenant_id, day, observed_at),
                )
                conn.commit()
        except (OSError, sqlite3.Error) as exc:
            raise SecurityLedgerError("persistent security ledger update failed") from exc
        return None

    def usage(self, *, tenant_id: str, day_utc: str) -> int:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT request_count FROM api_daily_quota
                    WHERE tenant_id=? AND day_utc=?
                    """,
                    (tenant_id, day_utc),
                ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise SecurityLedgerError("persistent security ledger read failed") from exc
        return 0 if row is None else int(row["request_count"])


_configured_ledger: SQLiteSecurityLedger | None = None
_configured_path: str | None = None


def get_configured_security_ledger(path: str | Path) -> SQLiteSecurityLedger:
    global _configured_ledger, _configured_path
    normalized = str(Path(path).expanduser())
    if _configured_ledger is None or _configured_path != normalized:
        _configured_ledger = SQLiteSecurityLedger(normalized)
        _configured_path = normalized
    return _configured_ledger


def reset_configured_security_ledger_for_tests() -> None:
    global _configured_ledger, _configured_path
    _configured_ledger = None
    _configured_path = None


__all__ = [
    "SQLiteSecurityLedger",
    "SecurityLedgerError",
    "get_configured_security_ledger",
    "reset_configured_security_ledger_for_tests",
]
