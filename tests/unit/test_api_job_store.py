from __future__ import annotations

from pathlib import Path

import asyncio
import json
import sqlite3

import pytest
from fastapi import BackgroundTasks

from api.job_store import SQLiteJobStore
from api.result_manifest import verify_result_manifest, write_result_manifest
from api.models import SimulationRequest


def test_sqlite_job_store_persists_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)

    created = store.create_job("job_1", {"target_name": "Chignolin"}, status="submitted")
    assert created["job_id"] == "job_1"
    assert created["status"] == "submitted"
    assert created["request"]["target_name"] == "Chignolin"

    store.update_job("job_1", status="failed", error="fail-closed runner not wired")

    reopened = SQLiteJobStore(db_path)
    record = reopened.get_job("job_1")
    assert record is not None
    assert record["status"] == "failed"
    assert record["error"] == "fail-closed runner not wired"
    assert reopened.job_exists("job_1") is True
    assert reopened.job_exists("missing") is False


def test_sqlite_job_store_redacts_sensitive_request_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)

    created = store.create_job(
        "job_private",
        {
            "target_name": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "runner_profile_id": "smoke",
            "runner_profile_params": {
                "ligands": ["CCO"],
                "metadata": {"ligand_smiles": "CCN"},
            },
        },
        status="submitted",
    )

    assert created["request"]["target_name"] == "ADRB2"
    assert created["request"]["pdb_content"]["redacted"] is True
    assert created["request"]["runner_profile_params"]["ligands"][0]["redacted"] is True
    assert created["request"]["runner_profile_params"]["metadata"]["ligand_smiles"]["redacted"] is True

    with sqlite3.connect(db_path) as conn:
        raw_request = conn.execute(
            "SELECT request_json FROM simulation_jobs WHERE job_id='job_private'"
        ).fetchone()[0]
    assert "ATOM      1" not in raw_request
    assert "CCO" not in raw_request
    assert "CCN" not in raw_request
    assert "sha256" in raw_request


def test_sqlite_job_store_acquires_jobs_with_worker_lease(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_1", {"target_name": "Chignolin"}, status="submitted")

    acquired = store.acquire_next_job("worker_a", lease_seconds=60)
    assert acquired is not None
    assert acquired["job_id"] == "job_1"
    assert acquired["status"] == "running"
    assert acquired["worker_id"] == "worker_a"
    assert acquired["attempt_count"] == 1
    assert acquired["lease_expires_at_utc"]
    assert acquired["heartbeat_at_utc"]

    assert store.acquire_next_job("worker_b", lease_seconds=60) is None

    refreshed = store.heartbeat_job("job_1", "worker_a", lease_seconds=60)
    assert refreshed is not None
    assert refreshed["worker_id"] == "worker_a"
    assert refreshed["heartbeat_at_utc"]

    assert store.heartbeat_job("job_1", "worker_b", lease_seconds=60) is None


def test_sqlite_job_store_retry_release_respects_max_attempts(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_retry", {"target_name": "Chignolin"}, status="submitted", max_attempts=2)

    first = store.acquire_next_job("worker_a", lease_seconds=60)
    assert first is not None
    assert first["attempt_count"] == 1

    retry_ready = store.release_job_for_retry("job_retry", "worker_a", error="transient runner failure")
    assert retry_ready is not None
    assert retry_ready["status"] == "retry_ready"
    assert retry_ready["worker_id"] == ""
    assert retry_ready["error"] == "transient runner failure"

    second = store.acquire_next_job("worker_b", lease_seconds=60)
    assert second is not None
    assert second["attempt_count"] == 2
    assert second["worker_id"] == "worker_b"

    failed = store.release_job_for_retry("job_retry", "worker_b", error="retry budget exhausted")
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["worker_id"] == ""
    assert failed["lease_expires_at_utc"] == ""
    assert failed["error"] == "retry budget exhausted"
    assert store.acquire_next_job("worker_c", lease_seconds=60) is None


def test_worker_process_next_job_retries_then_writes_failed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_worker_fail", {"target_name": "Chignolin"}, status="submitted", max_attempts=2)
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_worker_fail"),
        {"job_id": "job_worker_fail", "status": "submitted"},
    )

    async def _fail(job_id: str, request_data: dict) -> None:
        raise RuntimeError("validated runner still unavailable")

    first = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_a",
            runner=_fail,
            lease_seconds=60,
        )
    )
    assert first is not None
    assert first["status"] == "retry_ready"
    assert first["attempt_count"] == 1
    first_status = json.loads(Path(worker.job_status_path("job_worker_fail")).read_text(encoding="utf-8"))
    assert first_status["status"] == "retry_ready"
    assert "result_manifest" not in first_status

    second = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_b",
            runner=_fail,
            lease_seconds=60,
        )
    )
    assert second is not None
    assert second["status"] == "failed"
    assert second["attempt_count"] == 2
    assert second["result_manifest_path"]
    assert second["worker_id"] == ""

    manifest = json.loads(Path(second["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["error"] == "validated runner still unavailable"
    assert verify_result_manifest(
        manifest,
        signing_key=worker.settings.api_result_manifest_signing_key,
    )


def test_worker_process_next_job_writes_completed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_worker_ok", {"target_name": "Chignolin"}, status="submitted")
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_worker_ok"),
        {"job_id": "job_worker_ok", "status": "submitted"},
    )

    async def _success(job_id: str, request_data: dict) -> None:
        result_file = Path(worker.job_results_dir(job_id)) / "result.pdb"
        result_file.write_text("ATOM\n", encoding="utf-8")
        status_data = worker.read_status_file(worker.job_status_path(job_id))
        status_data.update({"job_id": job_id, "status": "completed", "result_file": str(result_file)})
        worker.write_status_file(worker.job_status_path(job_id), status_data)

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_a",
            runner=_success,
            lease_seconds=60,
        )
    )
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result_file"]
    assert completed["result_manifest_path"]
    assert completed["worker_id"] == ""

    manifest = json.loads(Path(completed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["result_file_sha256"]
    assert verify_result_manifest(
        manifest,
        signing_key=worker.settings.api_result_manifest_signing_key,
    )


def test_worker_extends_lease_while_runner_is_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    class HeartbeatSpyStore:
        def __init__(self, wrapped: SQLiteJobStore) -> None:
            self.wrapped = wrapped
            self.heartbeat_calls = 0

        def __getattr__(self, name: str):
            return getattr(self.wrapped, name)

        def heartbeat_job(self, job_id: str, worker_id: str, *, lease_seconds: int = 300):
            self.heartbeat_calls += 1
            return self.wrapped.heartbeat_job(job_id, worker_id, lease_seconds=lease_seconds)

    wrapped_store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    wrapped_store.create_job("job_heartbeat", {"target_name": "Chignolin"}, status="submitted")
    store = HeartbeatSpyStore(wrapped_store)
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_heartbeat"),
        {"job_id": "job_heartbeat", "status": "submitted"},
    )

    async def _slow_success(job_id: str, request_data: dict) -> None:
        await asyncio.sleep(0.16)
        result_file = Path(worker.job_results_dir(job_id)) / "result.pdb"
        result_file.write_text("ATOM\n", encoding="utf-8")
        status_data = worker.read_status_file(worker.job_status_path(job_id))
        status_data.update({"job_id": job_id, "status": "completed", "result_file": str(result_file)})
        worker.write_status_file(worker.job_status_path(job_id), status_data)

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_heartbeat",
            runner=_slow_success,
            lease_seconds=60,
            heartbeat_interval_seconds=0.05,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert store.heartbeat_calls >= 2
    assert wrapped_store.get_job("job_heartbeat")["worker_id"] == ""


def test_submit_simulation_defaults_to_queue_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "api_inline_worker_enabled", False)

    response = asyncio.run(
        main.submit_simulation(
            SimulationRequest(target_name="Chignolin", pdb_id="1abc", runner_profile_id="smoke"),
            BackgroundTasks(),
        )
    )

    record = store.get_job(response.job_id)
    assert record is not None
    assert record["status"] == "submitted"
    assert record["worker_id"] == ""
    assert record["attempt_count"] == 0

    status_path = tmp_path / "results" / response.job_id / "status.json"
    status_data = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_data == {"job_id": response.job_id, "status": "submitted"}


def test_result_manifest_signs_request_and_result_file(tmp_path: Path) -> None:
    result_file = tmp_path / "result.pdb"
    result_file.write_text("ATOM\n", encoding="utf-8")
    manifest_path = tmp_path / "result_manifest.json"

    manifest = write_result_manifest(
        manifest_path,
        job_id="job_manifest",
        request={"target_name": "Chignolin"},
        status="completed",
        result_file=str(result_file),
        signing_key="test-signing-key",
        key_id="test-key",
    )

    assert manifest_path.exists()
    assert manifest["signature_algorithm"] == "hmac-sha256"
    assert manifest["result_file_sha256"]
    assert verify_result_manifest(manifest, signing_key="test-signing-key") is True

    tampered = dict(manifest)
    tampered["status"] = "failed"
    assert verify_result_manifest(tampered, signing_key="test-signing-key") is False


def test_api_main_no_longer_declares_in_memory_job_dict() -> None:
    source = Path("api/main.py").read_text(encoding="utf-8")
    assert "jobs = {}" not in source
    assert "SQLiteJobStore" in source


def test_run_simulation_wrapper_updates_durable_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_wrapper", {"target_name": "Chignolin"}, status="submitted")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))

    async def _fail_closed(job_id: str, request_data: dict) -> None:
        raise RuntimeError("runner still fail-closed")

    monkeypatch.setattr(main, "run_simulation_async", _fail_closed)

    asyncio.run(main.run_simulation_async_wrapper("job_wrapper", {"target_name": "Chignolin"}))

    record = store.get_job("job_wrapper")
    assert record is not None
    assert record["status"] == "failed"
    assert record["error"] == "runner still fail-closed"
    assert record["result_manifest_path"]

    manifest_path = Path(record["result_manifest_path"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["error"] == "runner still fail-closed"
    assert verify_result_manifest(
        manifest,
        signing_key=main.settings.api_result_manifest_signing_key,
    )

    status_path = tmp_path / "results" / "job_wrapper" / "status.json"
    status_data = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_data["result_manifest"] == str(manifest_path)
