from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import asyncio
import json
import os
from pathlib import Path

from api.config import settings
from api.job_store import SQLiteJobStore, validate_job_id
from api.result_manifest import write_result_manifest
from api.tasks import run_simulation_async
from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle

SimulationRunner = Callable[[str, dict[str, Any]], Awaitable[None]]


def _sync_docking_ledger_if_needed(
    *,
    job_id: str,
    request_data: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
    worker_id: str = "",
) -> None:
    params = request_data.get("runner_profile_params", {})
    if not isinstance(params, dict):
        return
    docking_job_id = str(params.get("docking_job_id", "") or "").strip()
    if not docking_job_id:
        return
    try:
        from pathlib import Path

        from api.docking_dispatch import sync_ledger_from_simulation_result

        jobs_dir = Path(settings.results_storage_path) / "product_docking_jobs"
        sync_ledger_from_simulation_result(
            jobs_dir,
            docking_job_id,
            status=status,
            result_file=result_file,
            error=error,
            worker_id=worker_id,
        )
    except Exception:
        return


def job_results_dir(job_id: str) -> str:
    return os.path.join(settings.results_storage_path, validate_job_id(job_id))


def job_status_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "status.json")


def job_manifest_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "result_manifest.json")


def job_evidence_bundle_path(job_id: str) -> str:
    return os.path.join(job_results_dir(job_id), "evidence_bundle.json")


def read_status_file(status_file_path: str) -> dict[str, Any]:
    if not os.path.exists(status_file_path):
        return {}
    with open(status_file_path, "r", encoding="utf-8") as sf:
        return json.load(sf)


def read_json_object_file(file_path: str) -> dict[str, Any]:
    if not file_path or not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_status_file(status_file_path: str, status_data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(status_file_path), exist_ok=True)
    with open(status_file_path, "w", encoding="utf-8") as sf:
        json.dump(status_data, sf)


def write_job_result_manifest(
    *,
    job_id: str,
    request_data: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
) -> str:
    manifest_path = job_manifest_path(job_id)
    write_result_manifest(
        manifest_path,
        job_id=job_id,
        request=request_data,
        status=status,
        result_file=result_file,
        error=error,
        signing_key=settings.api_result_manifest_signing_key,
        key_id=settings.api_result_manifest_key_id,
    )
    return manifest_path


def write_job_evidence_bundle(
    *,
    job_id: str,
    request_data: dict[str, Any],
    result_manifest_path: str,
    status_data: dict[str, Any],
) -> tuple[str, str]:
    adopted_native = adopt_validated_runner_native_evidence_bundle(
        job_id=job_id,
        status_data=status_data,
    )
    if adopted_native is not None:
        return adopted_native
    result_manifest = read_json_object_file(result_manifest_path)
    result_payload = {}
    result_file = str(result_manifest.get("result_file", "") or status_data.get("result_file", "") or "")
    if result_file:
        result_payload = read_json_object_file(result_file)
    runner_execution = {}
    runner_execution_path = str(status_data.get("runner_execution", "") or "")
    if runner_execution_path:
        runner_execution = read_json_object_file(runner_execution_path)
    bundle_path = job_evidence_bundle_path(job_id)
    bundle = write_api_evidence_bundle(
        bundle_path,
        job_id=job_id,
        request=request_data,
        result_manifest=result_manifest,
        result_payload=result_payload,
        runner_execution=runner_execution,
        status_payload=status_data,
    )
    return bundle_path, bundle.fingerprint()


def adopt_validated_runner_native_evidence_bundle(
    *,
    job_id: str,
    status_data: dict[str, Any],
) -> tuple[str, str] | None:
    """Adopt a validated-runner-native EvidenceBundle as the final worker bundle.

    Returns ``(bundle_path, fingerprint)`` when a validated native bundle is recorded
    in the status file. Returns ``None`` when the runner did not produce or validate
    a native bundle so the caller can fall back to the API-generated review bundle.
    """
    if str(status_data.get("evidence_bundle_source", "") or "").strip() != "validated_runner_native":
        return None
    bundle_path_value = str(status_data.get("evidence_bundle", "") or "").strip()
    bundle_sha_value = str(status_data.get("evidence_bundle_sha256", "") or "").strip()
    if not bundle_path_value or not bundle_sha_value:
        return None
    if len(bundle_sha_value) != 64:
        return None
    bundle_path = Path(bundle_path_value)
    if not bundle_path.exists() or not bundle_path.is_file():
        return None
    payload = read_json_object_file(str(bundle_path))
    if not payload:
        return None
    try:
        from betelgeuze_ai_md.contracts import EvidenceBundle
        from betelgeuze_ai_md.contracts.errors import ContractValidationError

        bundle = EvidenceBundle(**payload)
    except (ContractValidationError, TypeError):
        return None
    if bundle.fingerprint() != bundle_sha_value:
        return None
    final_path = Path(job_evidence_bundle_path(job_id))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return str(final_path), bundle.fingerprint()


async def run_job_once(
    store: SQLiteJobStore,
    *,
    job_id: str,
    request_data: dict[str, Any],
    runner: SimulationRunner = run_simulation_async,
    worker_id: str = "",
    lease_seconds: int = 300,
    heartbeat_interval_seconds: float | None = None,
    retry_on_failure: bool = False,
) -> dict[str, Any]:
    """Run one job and persist status, manifest, and retry state."""
    if worker_id:
        store.heartbeat_job(job_id, worker_id, lease_seconds=lease_seconds)
    else:
        store.update_job(job_id, status="running")

    status_file_path = job_status_path(job_id)
    status_data = read_status_file(status_file_path)
    status_data.update({"job_id": job_id, "status": "running"})
    write_status_file(status_file_path, status_data)

    try:
        if worker_id:
            await _run_with_periodic_heartbeat(
                store,
                job_id=job_id,
                worker_id=worker_id,
                runner=runner,
                request_data=request_data,
                lease_seconds=lease_seconds,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
            )
        else:
            await runner(job_id, request_data)
        status_data = read_status_file(status_file_path)
        result_file = str(status_data.get("result_file", "") or "")
        manifest_path = write_job_result_manifest(
            job_id=job_id,
            request_data=request_data,
            status="completed",
            result_file=result_file,
        )
        bundle_path, bundle_hash = write_job_evidence_bundle(
            job_id=job_id,
            request_data=request_data,
            result_manifest_path=manifest_path,
            status_data=status_data,
        )
        status_data.update(
            {
                "job_id": job_id,
                "status": "completed",
                "result_manifest": manifest_path,
                "evidence_bundle": bundle_path,
                "evidence_bundle_sha256": bundle_hash,
            }
        )
        write_status_file(status_file_path, status_data)
        _sync_docking_ledger_if_needed(
            job_id=job_id,
            request_data=request_data,
            status="completed",
            result_file=result_file,
            worker_id=worker_id,
        )
        return store.update_job(
            job_id,
            status="completed",
            result_file=result_file,
            result_manifest_path=manifest_path,
            evidence_bundle_path=bundle_path,
            evidence_bundle_sha256=bundle_hash,
        )
    except Exception as exc:
        error = str(exc)
        _sync_docking_ledger_if_needed(
            job_id=job_id,
            request_data=request_data,
            status="failed",
            error=error,
            worker_id=worker_id,
        )
        if retry_on_failure and worker_id:
            released = store.release_job_for_retry(job_id, worker_id, error=error)
            if released is not None and released.get("status") == "retry_ready":
                status_data = read_status_file(status_file_path)
                status_data.update({"job_id": job_id, "status": "retry_ready", "error": error})
                write_status_file(status_file_path, status_data)
                return released

        manifest_path = write_job_result_manifest(
            job_id=job_id,
            request_data=request_data,
            status="failed",
            error=error,
        )
        status_data = read_status_file(status_file_path)
        status_data.update({"job_id": job_id, "status": "failed", "error": error, "result_manifest": manifest_path})
        write_status_file(status_file_path, status_data)
        return store.update_job(job_id, status="failed", error=error, result_manifest_path=manifest_path)


async def process_next_job_once(
    store: SQLiteJobStore,
    *,
    worker_id: str,
    runner: SimulationRunner = run_simulation_async,
    lease_seconds: int = 300,
    heartbeat_interval_seconds: float | None = None,
    retry_on_failure: bool = True,
) -> dict[str, Any] | None:
    acquired = store.acquire_next_job(worker_id, lease_seconds=lease_seconds)
    if acquired is None:
        return None
    return await run_job_once(
        store,
        job_id=str(acquired["job_id"]),
        request_data=dict(acquired.get("request") or {}),
        runner=runner,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        retry_on_failure=retry_on_failure,
    )


async def _run_with_periodic_heartbeat(
    store: SQLiteJobStore,
    *,
    job_id: str,
    worker_id: str,
    runner: SimulationRunner,
    request_data: dict[str, Any],
    lease_seconds: int,
    heartbeat_interval_seconds: float | None,
) -> None:
    interval = heartbeat_interval_seconds
    if interval is None:
        interval = max(1.0, min(float(lease_seconds) / 3.0, float(settings.api_worker_heartbeat_interval_seconds)))

    runner_task = asyncio.create_task(runner(job_id, request_data))
    try:
        while True:
            try:
                await asyncio.wait_for(asyncio.shield(runner_task), timeout=max(0.05, float(interval)))
                return
            except (TimeoutError, asyncio.TimeoutError):
                store.heartbeat_job(job_id, worker_id, lease_seconds=lease_seconds)
    finally:
        if not runner_task.done():
            runner_task.cancel()
