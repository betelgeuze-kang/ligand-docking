from __future__ import annotations

from pathlib import Path

from api.job_store import SQLITE_BUSY_TIMEOUT_MS, SQLiteJobStore


def test_sqlite_job_store_configures_busy_timeout_and_wal(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")

    with store._connect() as conn:
        busy_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    assert busy_timeout >= SQLITE_BUSY_TIMEOUT_MS
    assert journal_mode == "wal"


def test_sqlite_job_store_preserves_queue_lifecycle(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job-1", {"target_name": "ADRB2"})

    acquired = store.acquire_next_job("worker-1", lease_seconds=30)
    assert acquired is not None
    assert acquired["job_id"] == "job-1"
    assert acquired["status"] == "running"
    assert acquired["worker_id"] == "worker-1"

    updated = store.update_job("job-1", status="completed", result_file="result.json")
    assert updated["status"] == "completed"
    assert updated["worker_id"] == ""
