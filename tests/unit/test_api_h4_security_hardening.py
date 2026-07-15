from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.artifact_access import (
    open_confined_regular_file,
    read_confined_json_object,
    verify_completed_result_artifacts,
)
from api.atomic_job_admission import create_owned_job_atomic
from api.config import settings
from api.job_store import (
    EXECUTION_REQUEST_TRANSFORM_ID,
    SQLiteJobStore,
    canonical_request_sha256,
)
from api.request_identity import ProductRequestIdentity
from api.result_manifest import write_result_manifest
from api.security import (
    AUDIT_WRITE_FAILURES,
    BLOCKED_REQUESTS,
    HTTP_REQUESTS,
    ProductSecurityMiddleware,
)
from api.security_ledger import (
    SQLiteSecurityLedger,
    reset_configured_security_ledger_for_tests,
)
from api.tasks import run_simulation_async
from api.worker import read_status_file, write_job_result_manifest
from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle


def _identity(tenant_id: str = "tenant-a") -> ProductRequestIdentity:
    return ProductRequestIdentity(
        tenant_id=tenant_id,
        principal=f"token:{tenant_id}",
        authenticated=True,
        is_admin=False,
    )


def _configure_security(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    quota: int = 5000,
    max_payload: int = 1024,
) -> Path:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(settings, "product_api_audit_log_path", str(audit_path))
    monkeypatch.setattr(
        settings,
        "product_api_security_ledger_path",
        str(tmp_path / "security.sqlite3"),
    )
    monkeypatch.setattr(settings, "product_api_auth_required", False)
    monkeypatch.setattr(settings, "product_api_hosted_exposure_approved", False)
    monkeypatch.setattr(settings, "product_api_rate_limit_per_minute", 120)
    monkeypatch.setattr(settings, "product_api_tenant_daily_quota", quota)
    monkeypatch.setattr(settings, "product_api_max_payload_bytes", max_payload)
    reset_configured_security_ledger_for_tests()
    return audit_path


def _body_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ProductSecurityMiddleware)

    @app.post("/product/body")
    async def body(request: Request) -> dict[str, int]:
        first = await request.body()
        second = await request.body()
        return {"first": len(first), "second": len(second)}

    @app.get("/product/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _scope(*, headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/product/body",
        "raw_path": b"/product/body",
        "query_string": b"",
        "headers": headers or [(b"x-tenant-id", b"tenant-stream")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }


def _sent_response(sent: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    starts = [message for message in sent if message["type"] == "http.response.start"]
    assert len(starts) == 1
    body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return starts[0], json.loads(body)


def test_streamed_payload_limit_without_content_length_is_one_audited_413(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_path = _configure_security(tmp_path, monkeypatch, max_payload=5)
    app = _body_app()
    messages = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"def", "more_body": False},
        ]
    )
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return next(messages)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    request_labels = {
        "method": "POST",
        "path": "/product/body",
        "status_code": "413",
        "blocked_code": "payload_too_large",
    }
    before_requests = HTTP_REQUESTS.labels(**request_labels)._value.get()
    before_blocks = BLOCKED_REQUESTS.labels(code="payload_too_large")._value.get()

    asyncio.run(app(_scope(), receive, send))

    start, payload = _sent_response(sent)
    headers = dict(start["headers"])
    assert start["status"] == 413
    assert payload["code"] == "payload_too_large"
    assert headers[b"x-block-code"] == b"payload_too_large"
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert headers[b"x-frame-options"] == b"DENY"
    assert HTTP_REQUESTS.labels(**request_labels)._value.get() == before_requests + 1
    assert BLOCKED_REQUESTS.labels(code="payload_too_large")._value.get() == before_blocks + 1
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["status_code"] == 413
    assert rows[0]["tenant_id"] == "tenant-stream"


def test_exact_payload_limit_and_repeated_body_reads_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=5)
    response = TestClient(_body_app()).post("/product/body", content=b"abcde")
    assert response.status_code == 200
    assert response.json() == {"first": 5, "second": 5}


def test_content_length_over_limit_is_rejected_before_body_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=5)
    app = _body_app()
    receive_calls = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": b"abcdef", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        app(
            _scope(
                headers=[
                    (b"x-tenant-id", b"tenant-stream"),
                    (b"content-length", b"6"),
                ]
            ),
            receive,
            send,
        )
    )
    start, payload = _sent_response(sent)
    assert start["status"] == 413
    assert payload["code"] == "payload_too_large"
    assert receive_calls == 0


@pytest.mark.parametrize("content_length", ["invalid", "-1", "+1", " 1", "1,1"])
def test_invalid_content_length_is_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content_length: str,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=5)
    response = TestClient(_body_app()).post(
        "/product/body",
        content=b"",
        headers={"content-length": content_length},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_content_length"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_duplicate_content_length_is_rejected_before_body_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=5)
    receive_calls = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": b"a", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        _body_app()(
            _scope(
                headers=[
                    (b"x-tenant-id", b"tenant-stream"),
                    (b"content-length", b"1"),
                    (b"content-length", b"1"),
                ]
            ),
            receive,
            send,
        )
    )

    start, payload = _sent_response(sent)
    assert start["status"] == 400
    assert payload["code"] == "invalid_content_length"
    assert receive_calls == 0


def test_transfer_encoding_and_content_length_are_rejected_together(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=5)
    receive_calls = 0
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": b"a", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        _body_app()(
            _scope(
                headers=[
                    (b"x-tenant-id", b"tenant-stream"),
                    (b"transfer-encoding", b"chunked"),
                    (b"content-length", b"1"),
                ]
            ),
            receive,
            send,
        )
    )

    start, payload = _sent_response(sent)
    assert start["status"] == 400
    assert payload["code"] == "invalid_transfer_encoding"
    assert receive_calls == 0


def test_unread_chunked_body_is_still_limited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=5)
    downstream_called = False

    async def downstream(
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        nonlocal downstream_called
        downstream_called = True
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    app = ProductSecurityMiddleware(downstream)
    messages = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"def", "more_body": False},
        ]
    )
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return next(messages)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        app(
            _scope(
                headers=[
                    (b"x-tenant-id", b"tenant-stream"),
                    (b"transfer-encoding", b"chunked"),
                ]
            ),
            receive,
            send,
        )
    )

    start, payload = _sent_response(sent)
    assert start["status"] == 413
    assert payload["code"] == "payload_too_large"
    assert downstream_called is False


def test_empty_body_passes_zero_byte_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=0)
    response = TestClient(_body_app()).post("/product/body", content=b"")
    assert response.status_code == 200
    assert response.json() == {"first": 0, "second": 0}


def test_http_disconnect_is_audited_once_without_a_second_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_path = _configure_security(tmp_path, monkeypatch, max_payload=5)
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(_body_app()(_scope(), receive, send))
    assert sent == []
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["status_code"] == 499


def test_audit_path_failure_does_not_break_the_security_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch)
    non_directory = tmp_path / "not-a-directory"
    non_directory.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(
        settings,
        "product_api_audit_log_path",
        str(non_directory / "audit.jsonl"),
    )
    before = AUDIT_WRITE_FAILURES._value.get()

    response = TestClient(_body_app()).get("/product/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert AUDIT_WRITE_FAILURES._value.get() == before + 1


def test_overflow_is_rejected_before_downstream_can_start_a_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, max_payload=2)

    downstream_called = False

    async def downstream(
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        nonlocal downstream_called
        downstream_called = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()

    app = ProductSecurityMiddleware(downstream)
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"abc", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(app(_scope(), receive, send))
    start, payload = _sent_response(sent)
    assert start["status"] == 413
    assert payload["code"] == "payload_too_large"
    assert len([item for item in sent if item["type"] == "http.response.start"]) == 1
    assert downstream_called is False


def test_persistent_quota_survives_middleware_recreation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch, quota=1)
    first = TestClient(_body_app()).get(
        "/product/ping", headers={"X-Tenant-ID": "tenant-persistent"}
    )
    second = TestClient(_body_app()).get(
        "/product/ping", headers={"X-Tenant-ID": "tenant-persistent"}
    )
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "tenant_quota_exceeded"

    ledger = SQLiteSecurityLedger(tmp_path / "security.sqlite3")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert ledger.usage(tenant_id="tenant-persistent", day_utc=day) == 1


def test_persistent_quota_admission_is_atomic_across_concurrent_callers(
    tmp_path: Path,
) -> None:
    ledger = SQLiteSecurityLedger(tmp_path / "security.sqlite3")

    def consume() -> str | None:
        return ledger.consume(
            rate_key="tenant-concurrent:127.0.0.1",
            tenant_id="tenant-concurrent",
            rate_limit_per_minute=100,
            tenant_daily_quota=1,
            now=1_784_073_600.0,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: consume(), range(2)))

    assert outcomes.count(None) == 1
    assert outcomes.count("tenant_quota_exceeded") == 1
    assert ledger.usage(tenant_id="tenant-concurrent", day_utc="2026-07-15") == 1


def test_security_ledger_initialization_failure_is_fail_closed_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_security(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "product_api_security_ledger_path", str(tmp_path))
    reset_configured_security_ledger_for_tests()
    response = TestClient(_body_app()).get("/product/ping")
    assert response.status_code == 503
    assert response.json()["code"] == "security_ledger_unavailable"


def test_atomic_admission_persists_original_hash_owner_and_outbox(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    request = {
        "target_name": "ADRB2",
        "pdb_content": "ATOM secret",
        "runner_profile_params": {"ligands": ["CCO"]},
    }
    record = create_owned_job_atomic(store, _identity(), "job-atomic", request)
    assert record["request_sha256"] == canonical_request_sha256(request)
    assert record["request"]["pdb_content"]["redacted"] is True
    assert record["execution_request_sha256"] == canonical_request_sha256(
        record["request"]
    )
    assert record["execution_request_transform_id"] == EXECUTION_REQUEST_TRANSFORM_ID
    with sqlite3.connect(store.path) as conn:
        owner = conn.execute(
            "SELECT tenant_id FROM simulation_job_ownership WHERE job_id='job-atomic'"
        ).fetchone()[0]
        events = conn.execute(
            "SELECT COUNT(*) FROM simulation_job_outbox WHERE job_id='job-atomic'"
        ).fetchone()[0]
        provenance = conn.execute(
            """
            SELECT request_sha256, execution_request_sha256,
                   execution_request_transform_id
            FROM simulation_jobs WHERE job_id='job-atomic'
            """
        ).fetchone()
    assert owner == "tenant-a"
    assert events == 1
    assert provenance == (
        record["request_sha256"],
        record["execution_request_sha256"],
        EXECUTION_REQUEST_TRANSFORM_ID,
    )


def test_atomic_admission_rolls_back_owner_and_job_when_outbox_insert_fails(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE simulation_job_outbox")

    with pytest.raises(sqlite3.OperationalError):
        create_owned_job_atomic(
            store,
            _identity(),
            "job-rollback",
            {"target_name": "ADRB2"},
        )

    with sqlite3.connect(db_path) as conn:
        job_count = conn.execute(
            "SELECT COUNT(*) FROM simulation_jobs WHERE job_id='job-rollback'"
        ).fetchone()[0]
        owner_count = conn.execute(
            "SELECT COUNT(*) FROM simulation_job_ownership WHERE job_id='job-rollback'"
        ).fetchone()[0]
    assert job_count == 0
    assert owner_count == 0


def test_atomic_admission_returns_its_transaction_row_without_postcommit_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")

    def _postcommit_read_must_not_run(job_id: str):
        raise OSError("postcommit connection unavailable")

    monkeypatch.setattr(store, "get_job", _postcommit_read_must_not_run)
    record = create_owned_job_atomic(
        store,
        _identity(),
        "job-no-postcommit-read",
        {"target_name": "ADRB2"},
    )

    assert record["job_id"] == "job-no-postcommit-read"
    with sqlite3.connect(store.path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM simulation_jobs WHERE job_id='job-no-postcommit-read'"
        ).fetchone()[0] == 1


def test_worker_manifest_uses_durable_original_request_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = {"target_name": "ADRB2", "pdb_content": "ATOM secret"}
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    record = store.create_job("job-hash", raw)
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_result_manifest_signing_key", "test-key")
    monkeypatch.setattr(settings, "api_result_manifest_key_id", "test-key-id")
    manifest_path = write_job_result_manifest(
        job_id="job-hash",
        request_data=record["request"],
        request_sha256=record["request_sha256"],
        execution_request_sha256=record["execution_request_sha256"],
        execution_request_transform_id=record["execution_request_transform_id"],
        status="failed",
        error="bounded test",
    )
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert manifest["request_sha256"] == canonical_request_sha256(raw)
    assert manifest["request_sha256"] != canonical_request_sha256(record["request"])
    assert manifest["execution_request_sha256"] == canonical_request_sha256(
        record["request"]
    )
    assert (
        manifest["execution_request_transform_id"]
        == EXECUTION_REQUEST_TRANSFORM_ID
    )


def test_result_manifest_rejects_an_invalid_explicit_request_hash(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="request_sha256"):
        write_result_manifest(
            tmp_path / "result_manifest.json",
            job_id="job-invalid-hash",
            request={"target_name": "ADRB2"},
            request_sha256="not-a-sha256",
            status="failed",
            signing_key="unit-signing-key",
            key_id="unit-key",
        )


def _completed_fixture(
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], Path, str, str, bytes]:
    root = tmp_path / "results" / "job-artifacts"
    root.mkdir(parents=True)
    result_bytes = b'{"score": 1}'
    result_path = root / "result.json"
    result_path.write_bytes(result_bytes)
    evidence_path = root / "evidence_bundle.json"
    request = {"runner_profile_id": "smoke", "target_name": "ADRB2"}
    request_sha = canonical_request_sha256(request)
    execution_request_sha = canonical_request_sha256(request)
    signing_key = "unit-signing-key"
    key_id = "unit-key"
    manifest_path = root / "result_manifest.json"
    manifest = write_result_manifest(
        manifest_path,
        job_id="job-artifacts",
        request=request,
        request_sha256=request_sha,
        execution_request_sha256=execution_request_sha,
        execution_request_transform_id=EXECUTION_REQUEST_TRANSFORM_ID,
        status="completed",
        result_file=str(result_path),
        signing_key=signing_key,
        key_id=key_id,
    )
    evidence_bundle = write_api_evidence_bundle(
        evidence_path,
        job_id="job-artifacts",
        request=request,
        result_manifest=manifest,
        result_payload={"score": 1},
        status_payload={"status": "completed"},
    )
    evidence_sha = evidence_bundle.fingerprint()
    record = {
        "job_id": "job-artifacts",
        "status": "completed",
        "request_sha256": request_sha,
        "execution_request_sha256": execution_request_sha,
        "execution_request_transform_id": EXECUTION_REQUEST_TRANSFORM_ID,
        "result_file": str(result_path),
        "result_manifest_path": str(manifest_path),
        "evidence_bundle_path": str(evidence_path),
        "evidence_bundle_sha256": evidence_sha,
    }
    status = {
        "job_id": "job-artifacts",
        "status": "completed",
        "result_file": str(result_path),
        "result_manifest": str(manifest_path),
        "evidence_bundle": str(evidence_path),
        "evidence_bundle_sha256": evidence_sha,
    }
    return record, status, root, signing_key, key_id, result_bytes


def test_completed_artifact_snapshot_serves_the_verified_bytes(
    tmp_path: Path,
) -> None:
    record, status, root, signing_key, key_id, original = _completed_fixture(tmp_path)
    verified = verify_completed_result_artifacts(
        job_id="job-artifacts",
        record=record,
        status_data=status,
        result_root=root,
        signing_key=signing_key,
        expected_key_id=key_id,
        snapshot_result=True,
    )
    verified.result_path.write_text('{"score": 999}', encoding="utf-8")
    assert b"".join(verified.iter_result()) == original


def test_completed_artifacts_reject_tampering_and_symlink_escape(tmp_path: Path) -> None:
    record, status, root, signing_key, key_id, _ = _completed_fixture(tmp_path)
    Path(record["result_file"]).write_text('{"score": 999}', encoding="utf-8")
    with pytest.raises(Exception) as tampered:
        verify_completed_result_artifacts(
            job_id="job-artifacts",
            record=record,
            status_data=status,
            result_root=root,
            signing_key=signing_key,
            expected_key_id=key_id,
        )
    assert getattr(tampered.value, "status_code", None) == 403

    record, status, root, signing_key, key_id, _ = _completed_fixture(
        tmp_path / "symlink-case"
    )
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret": true}', encoding="utf-8")
    link = root / "link.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    record["result_file"] = str(link)
    status["result_file"] = str(link)
    with pytest.raises(Exception) as escaped:
        verify_completed_result_artifacts(
            job_id="job-artifacts",
            record=record,
            status_data=status,
            result_root=root,
            signing_key=signing_key,
            expected_key_id=key_id,
        )
    assert getattr(escaped.value, "status_code", None) == 403


def test_confined_open_keeps_original_file_when_directory_is_replaced(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    original = nested / "result.json"
    original.write_text('{"source": "original"}', encoding="utf-8")

    _, handle = open_confined_regular_file(root, original, label="result file")
    moved = root / "moved"
    nested.rename(moved)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "result.json").write_text('{"source": "outside"}', encoding="utf-8")
    try:
        nested.symlink_to(outside, target_is_directory=True)
    except OSError:
        handle.close()
        pytest.skip("symlinks unavailable")

    try:
        assert handle.read() == b'{"source": "original"}'
    finally:
        handle.close()


def test_confined_open_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    fifo = root / "status.json"
    try:
        os.mkfifo(fifo)
    except (AttributeError, OSError):
        pytest.skip("FIFOs unavailable")

    with pytest.raises(Exception) as rejected:
        open_confined_regular_file(root, fifo, label="job status")

    assert getattr(rejected.value, "status_code", None) == 403
    with pytest.raises(Exception) as status_rejected:
        read_status_file(str(fifo))
    assert getattr(status_rejected.value, "status_code", None) == 403


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_confined_json_status_rejects_link_to_outside_root(
    tmp_path: Path,
    link_kind: str,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    victim = tmp_path / "outside.json"
    victim.write_text('{"secret": true}', encoding="utf-8")
    status_path = root / "status.json"
    try:
        if link_kind == "symlink":
            status_path.symlink_to(victim)
        else:
            os.link(victim, status_path)
    except OSError:
        pytest.skip(f"{link_kind}s unavailable")

    with pytest.raises(Exception) as rejected:
        read_confined_json_object(root, status_path, label="job status")

    assert getattr(rejected.value, "status_code", None) == 403
    with pytest.raises(Exception) as status_rejected:
        read_status_file(str(status_path))
    assert getattr(status_rejected.value, "status_code", None) == 403


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_simulation_exception_status_replace_preserves_link_victim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    results_root = tmp_path / "results"
    job_id = f"job-{link_kind}"
    job_root = results_root / job_id
    job_root.mkdir(parents=True)
    victim = tmp_path / f"{link_kind}-victim.json"
    original = b'{"owner": "outside"}\n'
    victim.write_bytes(original)
    status_path = job_root / "status.json"
    try:
        if link_kind == "symlink":
            status_path.symlink_to(victim)
        else:
            os.link(victim, status_path)
    except OSError:
        pytest.skip(f"{link_kind}s unavailable")
    monkeypatch.setattr(settings, "results_storage_path", str(results_root))

    with pytest.raises(ValueError, match="runner_profile_id is required"):
        asyncio.run(run_simulation_async(job_id, {"target_name": "ADRB2"}))

    assert victim.read_bytes() == original
    assert not status_path.is_symlink()
    assert status_path.stat().st_nlink == 1
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == "failed"


@pytest.mark.parametrize("missing_side", ["status", "record"])
def test_completed_artifacts_require_status_and_durable_evidence_binding(
    tmp_path: Path,
    missing_side: str,
) -> None:
    record, status, root, signing_key, key_id, _ = _completed_fixture(tmp_path)
    if missing_side == "status":
        status["evidence_bundle_sha256"] = ""
    else:
        record["evidence_bundle_sha256"] = ""

    with pytest.raises(Exception) as rejected:
        verify_completed_result_artifacts(
            job_id="job-artifacts",
            record=record,
            status_data=status,
            result_root=root,
            signing_key=signing_key,
            expected_key_id=key_id,
        )

    assert getattr(rejected.value, "status_code", None) == 403


@pytest.mark.parametrize(
    ("record_field", "replacement"),
    [
        ("request_sha256", "a" * 64),
        ("execution_request_sha256", "b" * 64),
        ("execution_request_transform_id", "different_transform_v1"),
    ],
)
def test_completed_artifacts_require_both_signed_request_bindings(
    tmp_path: Path,
    record_field: str,
    replacement: str,
) -> None:
    record, status, root, signing_key, key_id, _ = _completed_fixture(tmp_path)
    record[record_field] = replacement

    with pytest.raises(Exception) as rejected:
        verify_completed_result_artifacts(
            job_id="job-artifacts",
            record=record,
            status_data=status,
            result_root=root,
            signing_key=signing_key,
            expected_key_id=key_id,
        )

    assert getattr(rejected.value, "status_code", None) == 403
