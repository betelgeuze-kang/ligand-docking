"""Shared SQLite connection policy for API security and queue ledgers."""

from __future__ import annotations

from pathlib import Path
import sqlite3


SQLITE_BUSY_TIMEOUT_MS = 5_000


def connect_sqlite(
    path: str | Path,
    *,
    timeout_seconds: float = 5.0,
    wal: bool = True,
) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(database), timeout=float(timeout_seconds))
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


__all__ = ["SQLITE_BUSY_TIMEOUT_MS", "connect_sqlite"]
