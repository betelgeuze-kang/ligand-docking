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
    assert completed["evidence_bundle_path"]
    assert completed["evidence_bundle_sha256"]
    assert len(completed["evidence_bundle_sha256"]) == 64
    assert completed["worker_id"] == ""

    manifest = json.loads(Path(completed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["result_file_sha256"]
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
    assert manifest["result_artifact_type"] == "json"
    assert manifest["result_file_media_type"] == "application/json"
    assert verify_result_manifest(manifest, signing_key="test-signing-key") is True

    tampered = json.loads(json.dumps(manifest))
    tampered["result_claim_metadata"]["claim_safe"] = True
    assert verify_result_manifest(tampered, signing_key="test-signing-key") is False
    tampered_force = json.loads(json.dumps(manifest))
    tampered_force["force_residual_summary"]["observed_caps_ready"] = False
    assert verify_result_manifest(tampered_force, signing_key="test-signing-key") is False


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

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    store.create_job("job_status", {"target_name": "Chignolin"}, status="completed")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))

    results_dir = tmp_path / "results" / "job_status"
    results_dir.mkdir(parents=True)
    manifest_path = results_dir / "result_manifest.json"
    bundle_path = results_dir / "evidence_bundle.json"
    manifest_path.write_text('{"status":"completed"}\n', encoding="utf-8")
    bundle_path.write_text('{"bundle_schema_version":"ai_md_evidence_bundle_v1"}\n', encoding="utf-8")
    main.write_status_file(
        main.job_status_path("job_status"),
        {
            "job_id": "job_status",
            "status": "completed",
            "result_manifest": str(manifest_path),
            "evidence_bundle": str(bundle_path),
            "evidence_bundle_sha256": "c" * 64,
        },
    )
    store.update_job(
        "job_status",
        status="completed",
        result_file=str(results_dir / "result.pdb"),
        result_manifest_path=str(manifest_path),
        evidence_bundle_path=str(bundle_path),
        evidence_bundle_sha256="c" * 64,
    )

    from fastapi.testclient import TestClient

    response = TestClient(main.app).get("/status/job_status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_manifest"] == str(manifest_path)
    assert payload["evidence_bundle"] == str(bundle_path)
    assert payload["evidence_bundle_sha256"] == "c" * 64


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
    store.create_job("job_no_bundle_hash", {"target_name": "Chignolin"}, status="completed")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))

    results_dir = tmp_path / "results" / "job_no_bundle_hash"
    results_dir.mkdir(parents=True)
    result_file = results_dir / "result.pdb"
    manifest_path = results_dir / "result_manifest.json"
    bundle_path = results_dir / "evidence_bundle.json"
    result_file.write_text("ATOM\n", encoding="utf-8")
    manifest_path.write_text('{"status":"completed"}\n', encoding="utf-8")
    bundle_path.write_text('{"bundle_schema_version":"ai_md_evidence_bundle_v1"}\n', encoding="utf-8")
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


def test_adopt_validated_runner_native_evidence_bundle_returns_none_when_file_missing(
    tmp_path: Path,
) -> None:
    import api.worker as worker

    missing_path = tmp_path / "does_not_exist.json"
    assert (
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_missing_file",
            status_data={
                "evidence_bundle": str(missing_path),
                "evidence_bundle_sha256": "a" * 64,
                "evidence_bundle_source": "validated_runner_native",
            },
        )
        is None
    )


def test_adopt_validated_runner_native_evidence_bundle_adopts_validated_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker
    from betelgeuze_ai_md.contracts import EvidenceBundle

    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    bundle = EvidenceBundle(
        bundle_id="native_adopted",
        project_id="native_adopted",
        ranked_shortlist=[],
        trajectory_summary={"frame_count": 0},
        backmapped_poses=[],
        interaction_report={},
        topology_report={
            "status": "not_assessed",
            "topology_fidelity": "placeholder_alanine",
            "claim_blockers": ["topology_validity_not_assessed"],
        },
        ai_residual_report={"residual_mode": "disabled", "uncertainty": 1.0, "abstained": True},
        failure_flags=["delivery_bundle_validation_not_attached"],
        source_hashes={
            "input_hash": "i" * 64,
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
    )
    bundle_path = tmp_path / "native" / "runner_native_bundle.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(
        json.dumps(bundle.to_dict(), sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fingerprint = bundle.fingerprint()

    adopted = worker.adopt_validated_runner_native_evidence_bundle(
        job_id="job_adopt",
        status_data={
            "evidence_bundle": str(bundle_path),
            "evidence_bundle_sha256": fingerprint,
            "evidence_bundle_source": "validated_runner_native",
        },
    )

    final_path = tmp_path / "results" / "job_adopt" / "evidence_bundle.json"
    assert adopted is not None
    assert adopted == (str(final_path), fingerprint)
    assert final_path.exists()
    assert json.loads(final_path.read_text(encoding="utf-8"))["bundle_id"] == "native_adopted"


def test_adopt_validated_runner_native_evidence_bundle_rejects_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    import api.worker as worker
    from betelgeuze_ai_md.contracts import EvidenceBundle

    bundle = EvidenceBundle(
        bundle_id="native_mismatch",
        project_id="native_mismatch",
        ranked_shortlist=[],
        trajectory_summary={"frame_count": 0},
        backmapped_poses=[],
        interaction_report={},
        topology_report={
            "status": "not_assessed",
            "topology_fidelity": "placeholder_alanine",
            "claim_blockers": ["topology_validity_not_assessed"],
        },
        ai_residual_report={"residual_mode": "disabled", "uncertainty": 1.0, "abstained": True},
        failure_flags=["delivery_bundle_validation_not_attached"],
        source_hashes={
            "input_hash": "i" * 64,
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
    )
    bundle_path = tmp_path / "evidence_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle.to_dict(), sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    assert (
        worker.adopt_validated_runner_native_evidence_bundle(
            job_id="job_mismatch",
            status_data={
                "evidence_bundle": str(bundle_path),
                "evidence_bundle_sha256": "0" * 64,
                "evidence_bundle_source": "validated_runner_native",
            },
        )
        is None
    )


def test_write_job_evidence_bundle_prefers_native_evidence_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.worker as worker
    from betelgeuze_ai_md.contracts import EvidenceBundle

    monkeypatch.setattr(worker.settings, "results_storage_path", str(tmp_path / "results"))
    bundle = EvidenceBundle(
        bundle_id="native_preferred",
        project_id="native_preferred",
        ranked_shortlist=[],
        trajectory_summary={"frame_count": 0},
        backmapped_poses=[],
        interaction_report={},
        topology_report={
            "status": "not_assessed",
            "topology_fidelity": "placeholder_alanine",
            "claim_blockers": ["topology_validity_not_assessed"],
        },
        ai_residual_report={"residual_mode": "disabled", "uncertainty": 1.0, "abstained": True},
        failure_flags=["delivery_bundle_validation_not_attached"],
        source_hashes={
            "input_hash": "i" * 64,
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
    )
    fingerprint = bundle.fingerprint()
    job_id = "job_native_preferred"
    bundle_path = tmp_path / "native" / job_id / "runner_bundle.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(
        json.dumps(bundle.to_dict(), sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    bundle_path_returned, fingerprint_returned = worker.write_job_evidence_bundle(
        job_id=job_id,
        request_data={"target_name": "Chignolin"},
        result_manifest_path="",
        status_data={
            "evidence_bundle": str(bundle_path),
            "evidence_bundle_sha256": fingerprint,
            "evidence_bundle_source": "validated_runner_native",
        },
    )

    final_path = tmp_path / "results" / job_id / "evidence_bundle.json"
    assert bundle_path_returned == str(final_path)
    assert fingerprint_returned == fingerprint
    assert final_path.exists()
    assert json.loads(final_path.read_text(encoding="utf-8"))["bundle_id"] == "native_preferred"
