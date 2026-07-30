from __future__ import annotations

from pathlib import Path

import asyncio
import hashlib
import json
import sqlite3
import threading

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


def test_sqlite_job_store_create_job_outbox_event_survives_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    store.create_job("job_outbox_create", {"target_name": "Chignolin"}, status="submitted")

    pending = store.list_pending_outbox_events()
    assert len(pending) == 1
    assert pending[0]["event_type"] == "job_created"
    assert pending[0]["job_id"] == "job_outbox_create"
    assert pending[0]["payload"] == {
        "job_id": "job_outbox_create",
        "status": "submitted",
        "target_name": "Chignolin",
    }

    reopened = SQLiteJobStore(db_path)
    recovered = reopened.list_pending_outbox_events()
    assert len(recovered) == 1
    assert recovered[0]["event_id"] == pending[0]["event_id"]
    assert recovered[0]["payload"]["job_id"] == "job_outbox_create"


def test_sqlite_job_store_create_job_if_absent_emits_outbox_event(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)

    _record, created = store.create_job_if_absent(
        "job_if_absent_outbox", {"target_name": "ADRB2"}, status="submitted"
    )
    assert created is True

    pending = store.list_pending_outbox_events()
    assert len(pending) == 1
    assert pending[0]["event_type"] == "job_created"
    assert pending[0]["payload"] == {
        "job_id": "job_if_absent_outbox",
        "status": "submitted",
        "target_name": "ADRB2",
    }

    # The durable creation event must survive a crash/reopen.
    reopened = SQLiteJobStore(db_path)
    recovered = reopened.list_pending_outbox_events()
    assert len(recovered) == 1
    assert recovered[0]["payload"]["job_id"] == "job_if_absent_outbox"


def test_sqlite_job_store_create_job_if_absent_duplicate_does_not_duplicate_outbox(
    tmp_path: Path,
) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    request = {"target_name": "ADRB2"}

    _first, created = store.create_job_if_absent("job_dup", request, status="submitted")
    assert created is True

    # An already-present job must be preserved and must not emit a second event.
    _second, created_again = store.create_job_if_absent("job_dup", request, status="submitted")
    assert created_again is False

    creation_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_created" and event["job_id"] == "job_dup"
    ]
    assert len(creation_events) == 1


def test_sqlite_job_store_create_job_if_absent_outbox_excludes_private_material(
    tmp_path: Path,
) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    private_request = {
        "target_name": "ADRB2",
        "ligand_smiles": "CCO",
        "protein_pdb": "ATOM      1  N   MET A   1",
    }

    _record, created = store.create_job_if_absent(
        "job_if_absent_private", private_request, status="submitted"
    )
    assert created is True

    pending = store.list_pending_outbox_events()
    assert len(pending) == 1
    serialized = json.dumps(pending[0]["payload"])
    assert "CCO" not in serialized
    assert "ATOM" not in serialized


def test_sqlite_job_store_terminal_outbox_event_delivered_idempotently_after_reopen(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    store.create_job("job_outbox_terminal", {"target_name": "Chignolin"}, status="submitted")
    store.update_job("job_outbox_terminal", status="failed", error="runner unavailable")

    status_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
    ]
    assert len(status_events) == 1
    event_id = int(status_events[0]["event_id"])
    assert status_events[0]["payload"]["job_id"] == "job_outbox_terminal"
    assert status_events[0]["payload"]["status"] == "failed"
    assert status_events[0]["payload"]["error"]["redacted"] is True
    assert status_events[0]["payload"]["error"]["redaction"] == "sha256"
    assert status_events[0]["payload"]["error"]["byte_length"] == len("runner unavailable")

    reopened = SQLiteJobStore(db_path)
    recovered = [
        event
        for event in reopened.list_pending_outbox_events()
        if int(event["event_id"]) == event_id
    ]
    assert len(recovered) == 1

    assert reopened.mark_outbox_event_delivered(event_id) is True
    assert reopened.mark_outbox_event_delivered(event_id) is True
    remaining_status_events = [
        event
        for event in reopened.list_pending_outbox_events()
        if int(event["event_id"]) == event_id
    ]
    assert remaining_status_events == []

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT delivery_state FROM simulation_job_outbox WHERE event_id=?",
            (event_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == "delivered"


def test_sqlite_job_store_retry_outbox_event_recoverable_after_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    store.create_job("job_outbox_retry", {"target_name": "Chignolin"}, status="submitted", max_attempts=3)
    acquired = store.acquire_next_job("worker_a", lease_seconds=60)
    assert acquired is not None

    released = store.release_job_for_retry(
        "job_outbox_retry",
        "worker_a",
        attempt_token=acquired["attempt_token"],
        error="transient failure",
    )
    assert released is not None
    assert released["status"] == "retry_ready"

    retry_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed" and event["payload"]["status"] == "retry_ready"
    ]
    assert len(retry_events) == 1
    event_id = int(retry_events[0]["event_id"])

    reopened = SQLiteJobStore(db_path)
    assert reopened.mark_outbox_event_recovered(event_id) is True
    assert reopened.mark_outbox_event_recovered(event_id) is True
    remaining_retry_events = [
        event
        for event in reopened.list_pending_outbox_events()
        if int(event["event_id"]) == event_id
    ]
    assert remaining_retry_events == []

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT delivery_state FROM simulation_job_outbox WHERE event_id=?",
            (event_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == "recovered"


def test_sqlite_job_store_outbox_payload_excludes_private_material(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    private_request = {
        "target_name": "ADRB2",
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
        "runner_profile_params": {
            "ligands": ["CCO"],
            "metadata": {"ligand_smiles": "CCN"},
        },
    }
    store.create_job("job_outbox_private", private_request, status="submitted")

    pending = store.list_pending_outbox_events()
    assert len(pending) == 1
    payload_json = json.dumps(pending[0]["payload"], sort_keys=True)
    assert "ATOM      1" not in payload_json
    assert "CCO" not in payload_json
    assert "CCN" not in payload_json
    assert "pdb_content" not in payload_json
    assert "runner_profile_params" not in payload_json
    assert pending[0]["payload"]["target_name"] == "ADRB2"

    with sqlite3.connect(db_path) as conn:
        raw_payload = conn.execute(
            "SELECT payload_json FROM simulation_job_outbox WHERE event_id=?",
            (pending[0]["event_id"],),
        ).fetchone()[0]
    assert "ATOM      1" not in raw_payload
    assert "CCO" not in raw_payload
    assert "CCN" not in raw_payload


def test_sqlite_job_store_outbox_status_error_is_redacted(tmp_path: Path) -> None:
    db_path = tmp_path / "api_jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    private_error = "runner failed while handling pdb_content=ATOM_PRIVATE and ligand_smiles=CCO_PRIVATE"
    store.create_job("job_outbox_error_private", {"target_name": "ADRB2"}, status="submitted")
    store.update_job("job_outbox_error_private", status="failed", error=private_error)

    status_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
    ]
    assert len(status_events) == 1
    payload = status_events[0]["payload"]
    assert payload["job_id"] == "job_outbox_error_private"
    assert payload["status"] == "failed"
    assert payload["error"]["redacted"] is True
    assert payload["error"]["redaction"] == "sha256"
    assert payload["error"]["byte_length"] == len(private_error.encode("utf-8"))
    assert len(payload["error"]["sha256"]) == 64

    payload_text = json.dumps(payload, sort_keys=True)
    assert "ATOM_PRIVATE" not in payload_text
    assert "CCO_PRIVATE" not in payload_text
    with sqlite3.connect(db_path) as conn:
        raw_payload = conn.execute(
            """
            SELECT payload_json
            FROM simulation_job_outbox
            WHERE event_type='job_status_changed'
            """
        ).fetchone()[0]
    assert "ATOM_PRIVATE" not in raw_payload
    assert "CCO_PRIVATE" not in raw_payload


def test_sqlite_job_store_repeated_terminal_update_does_not_duplicate_status_outbox(
    tmp_path: Path,
) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_outbox_terminal_once", {"target_name": "ADRB2"}, status="submitted")

    store.update_job("job_outbox_terminal_once", status="failed", error="first failure")
    store.update_job("job_outbox_terminal_once", status="failed", error="same terminal status")

    status_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
    ]
    assert len(status_events) == 1
    assert status_events[0]["payload"]["status"] == "failed"


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

    refreshed = store.heartbeat_job(
        "job_1",
        "worker_a",
        attempt_token=acquired["attempt_token"],
        lease_seconds=60,
    )
    assert refreshed is not None
    assert refreshed["worker_id"] == "worker_a"
    assert refreshed["heartbeat_at_utc"]

    assert (
        store.heartbeat_job(
            "job_1",
            "worker_b",
            attempt_token=acquired["attempt_token"],
            lease_seconds=60,
        )
        is None
    )


def test_sqlite_job_store_retry_release_respects_max_attempts(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_retry", {"target_name": "Chignolin"}, status="submitted", max_attempts=2)

    first = store.acquire_next_job("worker_a", lease_seconds=60)
    assert first is not None
    assert first["attempt_count"] == 1

    retry_ready = store.release_job_for_retry(
        "job_retry",
        "worker_a",
        attempt_token=first["attempt_token"],
        error="transient runner failure",
    )
    assert retry_ready is not None
    assert retry_ready["status"] == "retry_ready"
    assert retry_ready["worker_id"] == ""
    assert retry_ready["error"] == "transient runner failure"

    second = store.acquire_next_job("worker_b", lease_seconds=60)
    assert second is not None
    assert second["attempt_count"] == 2
    assert second["worker_id"] == "worker_b"

    failed = store.release_job_for_retry(
        "job_retry",
        "worker_b",
        attempt_token=second["attempt_token"],
        error="retry budget exhausted",
    )
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
    assert first_status["status"] == "submitted"
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
    assert completed["evidence_bundle_path"]
    assert completed["evidence_bundle_sha256"]
    assert len(completed["evidence_bundle_sha256"]) == 64
    assert completed["worker_id"] == ""

    manifest = json.loads(Path(completed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["result_file_sha256"]
    assert manifest["request_sha256"] == completed["request_sha256"]
    assert (
        manifest["execution_request_sha256"]
        == completed["execution_request_sha256"]
    )
    assert (
        manifest["execution_request_transform_id"]
        == completed["execution_request_transform_id"]
    )
    assert verify_result_manifest(
        manifest,
        signing_key=worker.settings.api_result_manifest_signing_key,
    )

    status = json.loads(Path(worker.job_status_path("job_worker_ok")).read_text(encoding="utf-8"))
    evidence_bundle = Path(status["evidence_bundle"])
    assert evidence_bundle.exists()
    assert len(status["evidence_bundle_sha256"]) == 64
    bundle = json.loads(evidence_bundle.read_text(encoding="utf-8"))
    assert bundle["bundle_schema_version"] == "ai_md_evidence_bundle_v1"
    assert bundle["verdict"]["claim_safe"] is False
    assert "delivery_bundle_validation_not_attached" in bundle["failure_flags"]
    assert (
        bundle["source_hashes"]["input_hash"]
        == completed["execution_request_sha256"]
    )
    assert (
        bundle["request_provenance"]["admission_request_sha256"]
        == completed["request_sha256"]
    )


def test_completed_api_uses_published_status_when_canonical_mirror_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_published_status", {"target_name": "ADRB2"})
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "api_job_store_path", str(store.path))
    monkeypatch.setattr(main, "job_store", store)
    worker.write_status_file(
        worker.job_status_path("job_published_status"),
        {"job_id": "job_published_status", "status": "submitted"},
    )

    async def _winner(job_id: str, request_data: dict) -> None:
        result_file = Path(worker.job_results_dir(job_id)) / "result.json"
        result_file.write_text('{"owner":"WINNER"}\n', encoding="utf-8")
        worker.write_status_file(
            worker.job_status_path(job_id),
            {
                "job_id": job_id,
                "status": "completed",
                "result_file": str(result_file),
            },
        )

    monkeypatch.setattr(worker, "_publish_canonical_status_best_effort", lambda *args: None)
    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker-published",
            runner=_winner,
            lease_seconds=60,
        )
    )
    assert completed is not None
    assert completed["status"] == "completed"
    canonical = json.loads(
        Path(worker.job_status_path("job_published_status")).read_text(encoding="utf-8")
    )
    assert canonical["status"] == "submitted"
    assert Path(completed["published_status_path"]).exists()

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    status_response = client.get("/status/job_published_status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["result_manifest_available"] is True
    result_response = client.get("/results/job_published_status")
    assert result_response.status_code == 200
    assert result_response.json() == {"owner": "WINNER"}

    other_attempt = (
        tmp_path
        / "results"
        / "job_published_status"
        / ".attempts"
        / "attempt-cross-mix"
    )
    other_attempt.mkdir()
    mixed_result = other_attempt / "result.json"
    mixed_result.write_text('{"owner":"MIXED"}\n', encoding="utf-8")
    published_status = json.loads(
        Path(completed["published_status_path"]).read_text(encoding="utf-8")
    )
    published_status["result_file"] = str(mixed_result)
    Path(completed["published_status_path"]).write_text(
        json.dumps(published_status),
        encoding="utf-8",
    )
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE simulation_jobs SET result_file=? WHERE job_id='job_published_status'",
            (str(mixed_result),),
        )
    mixed_response = client.get("/results/job_published_status")
    assert mixed_response.status_code == 403
    assert "published attempt" in mixed_response.json()["detail"]


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

        def heartbeat_job(
            self,
            job_id: str,
            worker_id: str,
            *,
            attempt_token: str,
            lease_seconds: int = 300,
        ):
            self.heartbeat_calls += 1
            return self.wrapped.heartbeat_job(
                job_id,
                worker_id,
                attempt_token=attempt_token,
                lease_seconds=lease_seconds,
            )

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
    assert manifest["result_file_suffix"] == ".pdb"
    assert manifest["result_artifact_type"] == "pdb"
    assert manifest["result_file_media_type"] == "chemical/x-pdb"
    assert verify_result_manifest(manifest, signing_key="test-signing-key") is True

    tampered = dict(manifest)
    tampered["status"] = "failed"
    assert verify_result_manifest(tampered, signing_key="test-signing-key") is False


def test_result_manifest_signs_runner_claim_metadata_from_json_result(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_file.write_text(
        json.dumps(
            {
                "claim_metadata": {
                    "topology_fidelity": "placeholder_alanine",
                    "ligand_topology_valid": True,
                    "hbond_evidence_status": "review",
                    "force_residual_applied": False,
                    "claim_safe": False,
                    "blocked_reason": "protein_topology_missing",
                },
                "hbond_evidence_summary": {
                    "schema_version": "hbond_evidence_v1",
                    "status": "review",
                    "evaluated_row_count": 1,
                    "claim_safe_row_count": 0,
                },
                "force_residual_shortlist": {
                    "schema_version": "force_residual_claim_metadata_v1",
                    "applied": False,
                    "reason": "disabled",
                    "policy_caps_ready": True,
                    "observed_caps_ready": True,
                },
                "score": {
                    "refine_element_model": "typed_pairwise",
                    "refine_element_fallback_used": False,
                    "refine_protein_element_source": "sequence_residue_element_proxy",
                    "refine_ligand_element_source": "rdkit_atom_elements_projected_to_model_coords",
                    "refine_ligand_element_topology_valid": True,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "result_manifest.json"

    manifest = write_result_manifest(
        manifest_path,
        job_id="job_manifest_claim_metadata",
        request={"target_name": "Chignolin"},
        status="completed",
        result_file=str(result_file),
        signing_key="test-signing-key",
        key_id="test-key",
    )

    assert manifest["result_claim_metadata"]["claim_safe"] is False
    assert manifest["result_claim_metadata"]["blocked_reason"] == "protein_topology_missing"
    assert manifest["hbond_evidence_summary"]["schema_version"] == "hbond_evidence_v1"
    assert manifest["force_residual_summary"]["schema_version"] == "force_residual_claim_metadata_v1"
    assert manifest["force_residual_summary"]["policy_caps_ready"] is True
    assert manifest["force_residual_summary"]["observed_caps_ready"] is True
    assert manifest["refine_element_summary"]["refine_element_model"] == "typed_pairwise"
    assert manifest["refine_element_summary"]["refine_element_fallback_used"] is False
    assert (
        manifest["refine_element_summary"]["refine_ligand_element_source"]
        == "rdkit_atom_elements_projected_to_model_coords"
    )
    assert manifest["result_artifact_type"] == "json"
    assert manifest["result_file_media_type"] == "application/json"
    assert verify_result_manifest(manifest, signing_key="test-signing-key") is True

    tampered = json.loads(json.dumps(manifest))
    tampered["result_claim_metadata"]["claim_safe"] = True
    assert verify_result_manifest(tampered, signing_key="test-signing-key") is False
    tampered_force = json.loads(json.dumps(manifest))
    tampered_force["force_residual_summary"]["observed_caps_ready"] = False
    assert verify_result_manifest(tampered_force, signing_key="test-signing-key") is False
    tampered_refine = json.loads(json.dumps(manifest))
    tampered_refine["refine_element_summary"]["refine_element_model"] = "single_element_proxy"
    assert verify_result_manifest(tampered_refine, signing_key="test-signing-key") is False


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


def test_sqlite_job_store_migrates_evidence_bundle_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_api_jobs.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE simulation_jobs (
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
        conn.execute(
            """
            INSERT INTO simulation_jobs(
                job_id, status, request_json, created_at_utc, updated_at_utc
            ) VALUES(?, ?, ?, ?, ?)
            """,
            ("legacy_job", "submitted", '{"target_name":"Chignolin"}', "2026-06-16T00:00:00+00:00", "2026-06-16T00:00:00+00:00"),
        )

    store = SQLiteJobStore(db_path)
    record = store.get_job("legacy_job")
    assert record is not None
    assert record["evidence_bundle_path"] == ""
    assert record["evidence_bundle_sha256"] == ""
    assert record["attempt_token"] == ""
    assert record["published_status_path"] == ""
    assert record["published_attempt_token_sha256"] == ""
    acquired = store.acquire_next_job("legacy-worker", lease_seconds=60)
    assert acquired is not None
    assert acquired["attempt_token"]


def test_sqlite_job_store_create_job_clears_result_pointers_on_recreate(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_reset", {"target_name": "Chignolin"}, status="submitted")
    store.update_job(
        "job_reset",
        status="completed",
        result_file="/tmp/result.pdb",
        result_manifest_path="/tmp/result_manifest.json",
        evidence_bundle_path="/tmp/evidence_bundle.json",
        evidence_bundle_sha256="a" * 64,
    )

    recreated = store.create_job("job_reset", {"target_name": "Chignolin"}, status="submitted")
    assert recreated["result_file"] == ""
    assert recreated["result_manifest_path"] == ""
    assert recreated["evidence_bundle_path"] == ""
    assert recreated["evidence_bundle_sha256"] == ""


def test_sqlite_job_store_update_job_persists_evidence_bundle_together(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_evidence", {"target_name": "Chignolin"}, status="submitted")

    updated = store.update_job(
        "job_evidence",
        status="completed",
        result_file="/tmp/result.pdb",
        result_manifest_path="/tmp/result_manifest.json",
        evidence_bundle_path="/tmp/evidence_bundle.json",
        evidence_bundle_sha256="b" * 64,
    )

    assert updated["result_manifest_path"] == "/tmp/result_manifest.json"
    assert updated["evidence_bundle_path"] == "/tmp/evidence_bundle.json"
    assert updated["evidence_bundle_sha256"] == "b" * 64

    reopened = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    record = reopened.get_job("job_evidence")
    assert record is not None
    assert record["evidence_bundle_path"] == "/tmp/evidence_bundle.json"
    assert record["evidence_bundle_sha256"] == "b" * 64

    manifest_only = store.update_job(
        "job_evidence",
        status="failed",
        error="runner failed after retry",
        result_manifest_path="/tmp/failed_manifest.json",
    )
    assert manifest_only["result_manifest_path"] == "/tmp/failed_manifest.json"
    assert manifest_only["evidence_bundle_path"] == ""
    assert manifest_only["evidence_bundle_sha256"] == ""


def test_get_status_exposes_evidence_bundle_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main
    from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    record = store.create_job(
        "job_status", {"target_name": "Chignolin"}, status="completed"
    )
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "api_result_manifest_signing_key", "test-signing-key")
    monkeypatch.setattr(main.settings, "api_result_manifest_key_id", "test-key-id")

    results_dir = tmp_path / "results" / "job_status"
    results_dir.mkdir(parents=True)
    result_path = results_dir / "result.pdb"
    manifest_path = results_dir / "result_manifest.json"
    bundle_path = results_dir / "evidence_bundle.json"
    result_path.write_text("ATOM\n", encoding="utf-8")
    manifest = write_result_manifest(
        manifest_path,
        job_id="job_status",
        request=record["request"],
        request_sha256=record["request_sha256"],
        execution_request_sha256=record["execution_request_sha256"],
        execution_request_transform_id=record["execution_request_transform_id"],
        status="completed",
        result_file=str(result_path),
        signing_key="test-signing-key",
        key_id="test-key-id",
    )
    evidence_bundle = write_api_evidence_bundle(
        bundle_path,
        job_id="job_status",
        request=record["request"],
        result_manifest=manifest,
        status_payload={"status": "completed"},
    )
    evidence_sha = evidence_bundle.fingerprint()
    main.write_status_file(
        main.job_status_path("job_status"),
        {
            "job_id": "job_status",
            "status": "completed",
            "result_file": str(result_path),
            "result_manifest": str(manifest_path),
            "evidence_bundle": str(bundle_path),
            "evidence_bundle_sha256": evidence_sha,
        },
    )
    store.update_job(
        "job_status",
        status="completed",
        result_file=str(result_path),
        result_manifest_path=str(manifest_path),
        evidence_bundle_path=str(bundle_path),
        evidence_bundle_sha256=evidence_sha,
    )

    from fastapi.testclient import TestClient

    response = TestClient(main.app).get("/status/job_status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_manifest"] is None
    assert payload["evidence_bundle"] is None
    assert payload["result_manifest_available"] is True
    assert payload["evidence_bundle_available"] is True
    assert payload["evidence_bundle_sha256"] == evidence_sha


def test_get_status_replaces_raw_worker_error_with_operator_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main

    raw_error = "runner token=super-secret failed for /private/operator/path"
    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_failed", {"target_name": "Chignolin"}, status="submitted")
    store.update_job("job_failed", status="failed", error=raw_error)
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    main.write_status_file(
        main.job_status_path("job_failed"),
        {"job_id": "job_failed", "status": "failed", "error": raw_error},
    )

    from fastapi.testclient import TestClient

    response = TestClient(main.app).get("/status/job_failed")
    assert response.status_code == 200
    payload_text = response.text
    payload = response.json()
    assert raw_error not in payload_text
    assert "super-secret" not in payload_text
    assert "/private/operator/path" not in payload_text
    assert payload["error_code"] == "job_execution_failed"
    assert payload["error_reference"] == hashlib.sha256(raw_error.encode()).hexdigest()


def test_get_results_fail_closed_without_evidence_bundle_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_raw_only", {"target_name": "Chignolin"}, status="completed")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))

    results_dir = tmp_path / "results" / "job_raw_only"
    results_dir.mkdir(parents=True)
    result_file = results_dir / "result.pdb"
    result_file.write_text("ATOM\n", encoding="utf-8")
    main.write_status_file(
        main.job_status_path("job_raw_only"),
        {
            "job_id": "job_raw_only",
            "status": "completed",
            "result_file": str(result_file),
        },
    )
    store.update_job("job_raw_only", status="completed", result_file=str(result_file))

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    response = client.get("/results/job_raw_only")
    assert response.status_code == 403
    assert "result manifest provenance" in response.json()["detail"]


def test_get_results_fail_closed_without_evidence_bundle_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    record = store.create_job(
        "job_no_bundle_hash", {"target_name": "Chignolin"}, status="completed"
    )
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "api_result_manifest_signing_key", "test-signing-key")
    monkeypatch.setattr(main.settings, "api_result_manifest_key_id", "test-key-id")

    results_dir = tmp_path / "results" / "job_no_bundle_hash"
    results_dir.mkdir(parents=True)
    result_file = results_dir / "result.pdb"
    manifest_path = results_dir / "result_manifest.json"
    bundle_path = results_dir / "evidence_bundle.json"
    result_file.write_text("ATOM\n", encoding="utf-8")
    bundle_path.write_text('{"bundle_schema_version":"ai_md_evidence_bundle_v1"}\n', encoding="utf-8")
    write_result_manifest(
        manifest_path,
        job_id="job_no_bundle_hash",
        request=record["request"],
        request_sha256=record["request_sha256"],
        execution_request_sha256=record["execution_request_sha256"],
        execution_request_transform_id=record["execution_request_transform_id"],
        status="completed",
        result_file=str(result_file),
        signing_key="test-signing-key",
        key_id="test-key-id",
    )
    main.write_status_file(
        main.job_status_path("job_no_bundle_hash"),
        {
            "job_id": "job_no_bundle_hash",
            "status": "completed",
            "result_file": str(result_file),
            "result_manifest": str(manifest_path),
            "evidence_bundle": str(bundle_path),
        },
    )
    store.update_job(
        "job_no_bundle_hash",
        status="completed",
        result_file=str(result_file),
        result_manifest_path=str(manifest_path),
        evidence_bundle_path=str(bundle_path),
        evidence_bundle_sha256="",
    )

    from fastapi.testclient import TestClient

    response = TestClient(main.app).get("/results/job_no_bundle_hash")
    assert response.status_code == 403
    assert "evidence bundle fingerprint" in response.json()["detail"]


def test_adopt_validated_runner_native_evidence_bundle_returns_none_without_provenance(
    tmp_path: Path,
) -> None:
    import api.worker as worker

    assert (
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_missing",
            status_data={"status": "completed"},
        )
        is None
    )


def test_adopt_validated_runner_native_evidence_bundle_rejects_partial_declaration(
    tmp_path: Path,
) -> None:
    import api.worker as worker

    with pytest.raises(worker.JobIntegrityError, match="unexpected native"):
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_partial_native",
            status_data={
                "evidence_bundle_source": "tampered_source",
                "evidence_bundle": str(tmp_path / "evidence_bundle.json"),
            },
        )


def test_adopt_validated_runner_native_evidence_bundle_rejects_declared_missing_file(
    tmp_path: Path,
) -> None:
    import api.worker as worker

    missing_path = tmp_path / "does_not_exist.json"
    with pytest.raises(worker.JobIntegrityError, match="file is missing"):
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_missing_file",
            status_data={
                "evidence_bundle": str(missing_path),
                "evidence_bundle_sha256": "a" * 64,
                "evidence_bundle_source": "validated_runner_native",
            },
        )


def _native_adoption_fixture(tmp_path: Path, job_id: str):
    from api.job_store import EXECUTION_REQUEST_TRANSFORM_ID
    from betelgeuze_ai_md.contracts import EvidenceBundle

    result_file = tmp_path / "native" / job_id / "runner_result.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text('{"ok":true}\n', encoding="utf-8")
    result_sha256 = hashlib.sha256(result_file.read_bytes()).hexdigest()
    admission_sha256 = "a" * 64
    execution_sha256 = "b" * 64
    native_manifest = {
        "job_id": job_id,
        "status": "completed",
        "request_sha256": execution_sha256,
        "execution_request_sha256": execution_sha256,
        "execution_request_transform_id": "identity_v1",
        "result_file": str(result_file),
        "result_file_sha256": result_sha256,
    }
    final_manifest = {
        **native_manifest,
        "request_sha256": admission_sha256,
        "execution_request_transform_id": EXECUTION_REQUEST_TRANSFORM_ID,
    }
    bundle = EvidenceBundle(
        bundle_id=f"api_{job_id}_evidence_bundle",
        project_id=job_id,
        ranked_shortlist=[],
        trajectory_summary={"frame_count": 0},
        backmapped_poses=[],
        interaction_report={},
        topology_report={
            "status": "not_assessed",
            "topology_fidelity": "placeholder_alanine",
            "claim_blockers": ["topology_validity_not_assessed"],
        },
        ai_residual_report={
            "residual_mode": "disabled",
            "uncertainty": 1.0,
            "abstained": True,
        },
        failure_flags=["delivery_bundle_validation_not_attached"],
        source_hashes={
            "input_hash": execution_sha256,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        viewer_assets=[],
        wetlab_handoff_table=[],
        verdict={
            "claim_safe": False,
            "verdict_label": "native_runner_review_only",
            "claim_scope": "restricted_local_delivery_proxy_refinement_only",
            "topology_fidelity": "placeholder_alanine",
            "accuracy_claim_grade": "restricted-local-delivery",
            "failure_flags": ["delivery_bundle_validation_not_attached"],
        },
        result_manifest=native_manifest,
        request_provenance={
            "admission_request_sha256": execution_sha256,
            "execution_request_sha256": execution_sha256,
            "execution_request_transform_id": "identity_v1",
        },
    )
    bundle_path = result_file.parent / "runner_native_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle.to_dict(), sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    status_data = {
        "result_file": str(result_file),
        "result_file_sha256": result_sha256,
        "evidence_bundle": str(bundle_path),
        "evidence_bundle_sha256": bundle.fingerprint(),
        "evidence_bundle_source": "validated_runner_native",
    }
    return (
        bundle,
        status_data,
        final_manifest,
        admission_sha256,
        execution_sha256,
        EXECUTION_REQUEST_TRANSFORM_ID,
    )


def test_adopt_validated_runner_native_evidence_bundle_adopts_validated_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    (
        native_bundle,
        status_data,
        final_manifest,
        admission_sha256,
        execution_sha256,
        transform_id,
    ) = _native_adoption_fixture(tmp_path, "job_adopt")

    adopted = worker.adopt_validated_runner_native_evidence_bundle(
        job_id="job_adopt",
        status_data=status_data,
        result_manifest=final_manifest,
        request_sha256=admission_sha256,
        execution_request_sha256=execution_sha256,
        execution_request_transform_id=transform_id,
    )

    final_path = tmp_path / "results" / "job_adopt" / "evidence_bundle.json"
    assert adopted is not None
    assert adopted[0] == str(final_path)
    assert adopted[1] != native_bundle.fingerprint()
    assert final_path.exists()
    payload = json.loads(final_path.read_text(encoding="utf-8"))
    assert payload["bundle_id"] == "api_job_adopt_evidence_bundle"
    assert payload["result_manifest"] == final_manifest
    assert payload["request_provenance"]["admission_request_sha256"] == admission_sha256


def test_adopt_validated_runner_native_evidence_bundle_rejects_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    import api.worker as worker
    _, status_data, final_manifest, admission, execution, transform = (
        _native_adoption_fixture(tmp_path, "job_mismatch")
    )
    status_data["evidence_bundle_sha256"] = "0" * 64
    with pytest.raises(worker.JobIntegrityError, match="fingerprint mismatch"):
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_mismatch",
            status_data=status_data,
            result_manifest=final_manifest,
            request_sha256=admission,
            execution_request_sha256=execution,
            execution_request_transform_id=transform,
        )


def test_adopt_validated_runner_native_evidence_bundle_rejects_overflow_json(
    tmp_path: Path,
) -> None:
    import api.worker as worker

    _, status_data, final_manifest, admission, execution, transform = (
        _native_adoption_fixture(tmp_path, "job_nonfinite_native")
    )
    bundle_path = Path(status_data["evidence_bundle"])
    raw = bundle_path.read_text(encoding="utf-8")
    bundle_path.write_text(
        raw.replace('"ranked_shortlist": []', '"ranked_shortlist": [1e309]'),
        encoding="utf-8",
    )

    with pytest.raises(worker.JobIntegrityError, match="not a JSON object"):
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_nonfinite_native",
            status_data=status_data,
            result_manifest=final_manifest,
            request_sha256=admission,
            execution_request_sha256=execution,
            execution_request_transform_id=transform,
        )


def test_write_job_evidence_bundle_prefers_native_evidence_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    job_id = "job_native_preferred"
    native_bundle, status_data, final_manifest, admission, execution, transform = (
        _native_adoption_fixture(tmp_path, job_id)
    )
    manifest_path = tmp_path / "native" / job_id / "result_manifest.json"
    manifest_path.write_text(json.dumps(final_manifest) + "\n", encoding="utf-8")

    bundle_path_returned, fingerprint_returned = worker.write_job_evidence_bundle(
        job_id=job_id,
        request_data={"target_name": "Chignolin"},
        result_manifest_path=str(manifest_path),
        status_data=status_data,
        request_sha256=admission,
        execution_request_sha256=execution,
        execution_request_transform_id=transform,
    )

    final_path = tmp_path / "results" / job_id / "evidence_bundle.json"
    assert bundle_path_returned == str(final_path)
    assert fingerprint_returned != native_bundle.fingerprint()
    assert final_path.exists()
    payload = json.loads(final_path.read_text(encoding="utf-8"))
    assert payload["bundle_id"] == f"api_{job_id}_evidence_bundle"
    assert payload["result_manifest"] == final_manifest


def test_worker_rejects_execution_payload_hash_mismatch_without_retrying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    raw_request = {"target_name": "ADRB2", "pdb_content": "ATOM private"}
    store.create_job("job_integrity", raw_request, max_attempts=3)
    acquired = store.acquire_next_job("worker-integrity", lease_seconds=60)
    assert acquired is not None
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_integrity"),
        {"job_id": "job_integrity", "status": "submitted"},
    )
    runner_calls = 0

    async def _must_not_run(job_id: str, request_data: dict) -> None:
        nonlocal runner_calls
        runner_calls += 1

    tampered_request = dict(acquired["request"])
    tampered_request["target_name"] = "tampered"
    failed = asyncio.run(
        worker.run_job_once(
            store,
            job_id="job_integrity",
            request_data=tampered_request,
            runner=_must_not_run,
            worker_id="worker-integrity",
            attempt_token=acquired["attempt_token"],
            lease_seconds=60,
            retry_on_failure=True,
        )
    )

    assert runner_calls == 0
    assert failed["status"] == "failed"
    assert failed["attempt_count"] == 1
    assert failed["error"] == "execution request integrity verification failed"
    assert failed["result_manifest_path"]
    manifest = json.loads(Path(failed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["request_sha256"] == failed["request_sha256"]
    assert manifest["execution_request_sha256"] == failed["execution_request_sha256"]
    assert not any(
        event["payload"].get("status") == "retry_ready"
        for event in store.list_pending_outbox_events()
    )


@pytest.mark.parametrize(
    ("max_attempts", "expected_status"),
    [(1, "failed"), (2, "retry_ready")],
)
def test_worker_status_setup_failure_reaches_durable_failure_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    max_attempts: int,
    expected_status: str,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job(
        "job_status_failure",
        {"target_name": "ADRB2"},
        max_attempts=max_attempts,
    )
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    runner_calls = 0

    async def _must_not_run(job_id: str, request_data: dict) -> None:
        nonlocal runner_calls
        runner_calls += 1

    def _status_write_fails(path: str, payload: dict) -> None:
        raise OSError("status storage unavailable")

    monkeypatch.setattr(worker, "write_status_file", _status_write_fails)
    failed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker-status-failure",
            runner=_must_not_run,
            lease_seconds=60,
            retry_on_failure=True,
        )
    )

    assert runner_calls == 0
    assert failed is not None
    assert failed["status"] == expected_status
    assert failed["worker_id"] == ""
    assert failed["error"] == "status storage unavailable"
    if expected_status == "failed":
        assert store.acquire_next_job("worker-later", lease_seconds=60) is None
    else:
        assert store.acquire_next_job("worker-later", lease_seconds=60) is not None


def test_stale_worker_cannot_overwrite_new_lease_owner_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_two_workers", {"target_name": "ADRB2"}, max_attempts=2)
    first = store.acquire_next_job("worker-a", lease_seconds=60)
    assert first is not None
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' WHERE job_id='job_two_workers'"
        )
    second = store.acquire_next_job("worker-b", lease_seconds=60)
    assert second is not None
    assert second["worker_id"] == "worker-b"
    assert second["attempt_count"] == 2

    stale_terminal = store.update_job(
        "job_two_workers",
        status="completed",
        result_file="/tmp/stale-result.pdb",
        expected_worker_id="worker-a",
        expected_attempt_token=first["attempt_token"],
    )
    assert stale_terminal is None
    assert store.get_job("job_two_workers")["worker_id"] == "worker-b"

    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_two_workers"),
        {"job_id": "job_two_workers", "status": "submitted"},
    )
    stale_runner_calls = 0

    async def _stale_runner(job_id: str, request_data: dict) -> None:
        nonlocal stale_runner_calls
        stale_runner_calls += 1

    with pytest.raises(worker.JobLeaseLostError):
        asyncio.run(
            worker.run_job_once(
                store,
                job_id="job_two_workers",
                request_data=dict(first["request"]),
                runner=_stale_runner,
                worker_id="worker-a",
                attempt_token=first["attempt_token"],
                lease_seconds=60,
            )
        )
    assert stale_runner_calls == 0

    async def _winner(job_id: str, request_data: dict) -> None:
        result_path = Path(worker.job_results_dir(job_id)) / "winner.pdb"
        result_path.write_text("ATOM WINNER\n", encoding="utf-8")
        status = worker.read_status_file(worker.job_status_path(job_id))
        status.update({"status": "completed", "result_file": str(result_path)})
        worker.write_status_file(worker.job_status_path(job_id), status)

    completed = asyncio.run(
        worker.run_job_once(
            store,
            job_id="job_two_workers",
            request_data=dict(second["request"]),
            runner=_winner,
            worker_id="worker-b",
            attempt_token=second["attempt_token"],
            lease_seconds=60,
        )
    )
    assert completed["status"] == "completed"
    assert completed["result_file"].endswith("winner.pdb")
    terminal_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
        and event["payload"].get("status") == "completed"
    ]
    assert len(terminal_events) == 1


def test_same_worker_reacquisition_invalidates_old_attempt_token(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_same_worker", {"target_name": "ADRB2"}, max_attempts=2)
    first = store.acquire_next_job("stable-worker", lease_seconds=60)
    assert first is not None
    assert first["attempt_token"]

    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' "
            "WHERE job_id='job_same_worker'"
        )
    second = store.acquire_next_job("stable-worker", lease_seconds=60)
    assert second is not None
    assert second["attempt_token"] != first["attempt_token"]
    assert second["attempt_count"] == 2

    assert (
        store.heartbeat_job(
            "job_same_worker",
            "stable-worker",
            attempt_token=first["attempt_token"],
            lease_seconds=60,
        )
        is None
    )
    assert (
        store.release_job_for_retry(
            "job_same_worker",
            "stable-worker",
            attempt_token=first["attempt_token"],
            error="stale",
        )
        is None
    )
    assert (
        store.update_job(
            "job_same_worker",
            status="completed",
            result_file="/tmp/stale.pdb",
            expected_worker_id="stable-worker",
            expected_attempt_token=first["attempt_token"],
        )
        is None
    )
    current = store.get_job("job_same_worker")
    assert current is not None
    assert current["status"] == "running"
    assert current["attempt_token"] == second["attempt_token"]

    completed = store.update_job(
        "job_same_worker",
        status="completed",
        result_file="/tmp/winner.pdb",
        expected_worker_id="stable-worker",
        expected_attempt_token=second["attempt_token"],
    )
    assert completed is not None
    assert completed["status"] == "completed"
    terminal_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
        and event["payload"].get("status") == "completed"
    ]
    assert len(terminal_events) == 1


def test_stale_attempt_late_write_cannot_replace_same_worker_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_late_write", {"target_name": "ADRB2"}, max_attempts=2)
    first = store.acquire_next_job("stable-worker", lease_seconds=60)
    assert first is not None
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_late_write"),
        {"job_id": "job_late_write", "status": "submitted"},
    )

    async def _scenario() -> tuple[dict, Path, Path]:
        started = asyncio.Event()
        cancelled = asyncio.Event()
        allow_late_write = asyncio.Event()
        stale_attempt_dir: Path | None = None

        async def _stale_runner(job_id: str, request_data: dict) -> None:
            nonlocal stale_attempt_dir
            stale_attempt_dir = Path(worker.job_results_dir(job_id))
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                await allow_late_write.wait()
                stale_result = stale_attempt_dir / "result.pdb"
                stale_result.write_text("ATOM STALE\n", encoding="utf-8")
                worker.write_status_file(
                    str(stale_attempt_dir / "status.json"),
                    {
                        "job_id": job_id,
                        "status": "completed",
                        "result_file": str(stale_result),
                    },
                )

        stale_task = asyncio.create_task(
            worker.run_job_once(
                store,
                job_id="job_late_write",
                request_data=dict(first["request"]),
                runner=_stale_runner,
                worker_id="stable-worker",
                attempt_token=first["attempt_token"],
                lease_seconds=60,
                heartbeat_interval_seconds=0.05,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        with sqlite3.connect(store.path) as conn:
            conn.execute(
                "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' "
                "WHERE job_id='job_late_write'"
            )
        second = store.acquire_next_job("stable-worker", lease_seconds=60)
        assert second is not None

        async def _winner(job_id: str, request_data: dict) -> None:
            winner_dir = Path(worker.job_results_dir(job_id))
            winner_result = winner_dir / "result.pdb"
            winner_result.write_text("ATOM WINNER\n", encoding="utf-8")
            worker.write_status_file(
                worker.job_status_path(job_id),
                {
                    "job_id": job_id,
                    "status": "completed",
                    "result_file": str(winner_result),
                },
            )

        winner = await worker.run_job_once(
            store,
            job_id="job_late_write",
            request_data=dict(second["request"]),
            runner=_winner,
            worker_id="stable-worker",
            attempt_token=second["attempt_token"],
            lease_seconds=60,
        )
        await asyncio.wait_for(cancelled.wait(), timeout=1)
        allow_late_write.set()
        with pytest.raises(worker.JobLeaseLostError):
            await asyncio.wait_for(stale_task, timeout=1)
        assert stale_attempt_dir is not None
        return winner, stale_attempt_dir, Path(winner["result_file"]).parent

    winner, stale_attempt_dir, winner_attempt_dir = asyncio.run(_scenario())
    assert stale_attempt_dir != winner_attempt_dir
    assert (stale_attempt_dir / "result.pdb").read_text(encoding="utf-8") == "ATOM STALE\n"
    assert Path(winner["result_file"]).read_text(encoding="utf-8") == "ATOM WINNER\n"
    current = store.get_job("job_late_write")
    assert current is not None
    assert current["result_file"] == winner["result_file"]
    published_status = json.loads(
        Path(current["published_status_path"]).read_text(encoding="utf-8")
    )
    assert published_status["result_file"] == winner["result_file"]
    canonical_status = json.loads(
        Path(worker.job_status_path("job_late_write")).read_text(encoding="utf-8")
    )
    assert canonical_status["result_file"] == winner["result_file"]
    terminal_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
        and event["payload"].get("status") == "completed"
    ]
    assert len(terminal_events) == 1


def test_periodic_heartbeat_loss_cancels_runner_without_retry_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_heartbeat_loss", {"target_name": "ADRB2"}, max_attempts=2)
    acquired = store.acquire_next_job("worker-a", lease_seconds=60)
    assert acquired is not None
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_heartbeat_loss"),
        {"job_id": "job_heartbeat_loss", "status": "submitted"},
    )

    async def _scenario() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def _slow_runner(job_id: str, request_data: dict) -> None:
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        worker_a = asyncio.create_task(
            worker.run_job_once(
                store,
                job_id="job_heartbeat_loss",
                request_data=dict(acquired["request"]),
                runner=_slow_runner,
                worker_id="worker-a",
                attempt_token=acquired["attempt_token"],
                lease_seconds=60,
                heartbeat_interval_seconds=0.05,
                retry_on_failure=True,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        with sqlite3.connect(store.path) as conn:
            conn.execute(
                "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' WHERE job_id='job_heartbeat_loss'"
            )
        replacement = store.acquire_next_job("worker-b", lease_seconds=60)
        assert replacement is not None
        assert replacement["worker_id"] == "worker-b"
        with pytest.raises(worker.JobLeaseLostError):
            await asyncio.wait_for(worker_a, timeout=1)
        assert cancelled.is_set()

    asyncio.run(_scenario())
    current = store.get_job("job_heartbeat_loss")
    assert current is not None
    assert current["status"] == "running"
    assert current["worker_id"] == "worker-b"
    assert not any(
        event["payload"].get("status") in {"retry_ready", "failed"}
        for event in store.list_pending_outbox_events()
    )


def test_late_thread_write_is_confined_after_lease_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_tier_thread", {"target_name": "ADRB2"}, max_attempts=2)
    first = store.acquire_next_job("stable-tier-worker", lease_seconds=60)
    assert first is not None
    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    worker.write_status_file(
        worker.job_status_path("job_tier_thread"),
        {"job_id": "job_tier_thread", "status": "submitted"},
    )
    started = threading.Event()
    allow_late_write = threading.Event()
    late_write_done = threading.Event()
    stale_dir: list[Path] = []

    def _blocking_late_writer(job_id: str) -> None:
        attempt_dir = Path(worker.job_results_dir(job_id))
        stale_dir.append(attempt_dir)
        started.set()
        assert allow_late_write.wait(timeout=5)
        result_file = attempt_dir / "tier_result.json"
        result_file.write_text('{"owner":"STALE"}\n', encoding="utf-8")
        (attempt_dir / "status.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "result_file": str(result_file),
                }
            ),
            encoding="utf-8",
        )
        late_write_done.set()

    async def _stale_thread_runner(job_id: str, request_data: dict) -> None:
        del request_data
        await asyncio.to_thread(_blocking_late_writer, job_id)

    async def _scenario() -> dict:
        stale_task = asyncio.create_task(
            worker.run_job_once(
                store,
                job_id="job_tier_thread",
                request_data=dict(first["request"]),
                runner=_stale_thread_runner,
                worker_id="stable-tier-worker",
                attempt_token=first["attempt_token"],
                lease_seconds=60,
                heartbeat_interval_seconds=0.05,
            )
        )
        deadline = asyncio.get_running_loop().time() + 1
        while not started.is_set():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("late writer thread did not start")
            await asyncio.sleep(0.01)
        with sqlite3.connect(store.path) as conn:
            conn.execute(
                "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' "
                "WHERE job_id='job_tier_thread'"
            )
        second = store.acquire_next_job("stable-tier-worker", lease_seconds=60)
        assert second is not None
        with pytest.raises(worker.JobLeaseLostError):
            await asyncio.wait_for(stale_task, timeout=1)

        async def _winner(job_id: str, request_data: dict) -> None:
            attempt_dir = Path(worker.job_results_dir(job_id))
            result_file = attempt_dir / "winner.json"
            result_file.write_text('{"owner":"WINNER"}\n', encoding="utf-8")
            worker.write_status_file(
                worker.job_status_path(job_id),
                {
                    "job_id": job_id,
                    "status": "completed",
                    "result_file": str(result_file),
                },
            )

        winner = await worker.run_job_once(
            store,
            job_id="job_tier_thread",
            request_data=dict(second["request"]),
            runner=_winner,
            worker_id="stable-tier-worker",
            attempt_token=second["attempt_token"],
            lease_seconds=60,
        )
        allow_late_write.set()
        deadline = asyncio.get_running_loop().time() + 1
        while not late_write_done.is_set():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("late writer thread did not finish its write")
            await asyncio.sleep(0.01)
        return winner

    winner = asyncio.run(_scenario())
    assert stale_dir
    assert stale_dir[0] != Path(winner["result_file"]).parent
    assert (stale_dir[0] / "tier_result.json").read_text(encoding="utf-8") == '{"owner":"STALE"}\n'
    assert Path(winner["result_file"]).read_text(encoding="utf-8") == '{"owner":"WINNER"}\n'
    current = store.get_job("job_tier_thread")
    assert current is not None
    assert current["result_file"] == winner["result_file"]
    canonical_status = json.loads(
        Path(worker.job_status_path("job_tier_thread")).read_text(encoding="utf-8")
    )
    assert canonical_status["result_file"] == winner["result_file"]


def test_expired_final_attempt_is_recovered_as_failed(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job("job_expired_final", {"target_name": "ADRB2"}, max_attempts=1)
    assert store.acquire_next_job("worker-a", lease_seconds=60) is not None
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' WHERE job_id='job_expired_final'"
        )

    assert store.acquire_next_job("worker-b", lease_seconds=60) is None
    recovered = store.get_job("job_expired_final")
    assert recovered is not None
    assert recovered["status"] == "failed"
    assert recovered["worker_id"] == ""
    assert recovered["error"] == "worker lease expired after retry budget exhausted"
    assert store.acquire_next_job("worker-c", lease_seconds=60) is None
    recovered_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["event_type"] == "job_status_changed"
        and event["payload"].get("status") == "failed"
    ]
    assert len(recovered_events) == 1


def test_simulate_status_failure_happens_before_db_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "api_inline_worker_enabled", False)

    def _status_create_fails(job_id: str):
        raise OSError("status admission unavailable")

    monkeypatch.setattr(main, "create_initial_status_file", _status_create_fails)
    with pytest.raises(OSError, match="status admission unavailable"):
        asyncio.run(
            main.submit_simulation(
                SimulationRequest(
                    target_name="Chignolin",
                    pdb_id="1abc",
                    runner_profile_id="smoke",
                ),
                BackgroundTasks(),
            )
        )
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM simulation_jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM simulation_job_outbox").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM simulation_job_ownership").fetchone()[0] == 0


def test_simulate_db_failure_cleans_only_its_exclusive_status_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(main.settings, "api_inline_worker_enabled", False)
    receipts = []
    real_create = main.create_initial_status_file

    def _capture_status(job_id: str):
        receipt = real_create(job_id)
        receipts.append(receipt)
        return receipt

    def _db_admission_fails(*args, **kwargs):
        raise sqlite3.OperationalError("forced admission failure")

    monkeypatch.setattr(main, "create_initial_status_file", _capture_status)
    monkeypatch.setattr(main, "create_simulation_job_for_identity", _db_admission_fails)
    with pytest.raises(sqlite3.OperationalError, match="forced admission failure"):
        asyncio.run(
            main.submit_simulation(
                SimulationRequest(
                    target_name="Chignolin",
                    pdb_id="1abc",
                    runner_profile_id="smoke",
                ),
                BackgroundTasks(),
            )
        )
    assert len(receipts) == 1
    assert not Path(receipts[0].path).exists()
    assert store.list_pending_outbox_events() == []


def test_initial_status_cleanup_preserves_a_replaced_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker

    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    receipt = worker.create_initial_status_file("job-inode")
    status_path = Path(receipt.path)
    status_path.unlink()
    status_path.write_text('{"replacement":true}\n', encoding="utf-8")

    assert worker.cleanup_initial_status_file(receipt) is False
    assert json.loads(status_path.read_text(encoding="utf-8")) == {"replacement": True}
